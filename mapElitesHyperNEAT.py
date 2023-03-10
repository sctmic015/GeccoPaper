import math
import pickle
import neat
import visualize
import neat.nn
import numpy as np
import multiprocessing
import os
import sys
import visualize as vz
import shutil
from hexapod.controllers.hyperNEATController import Controller, reshape, stationary
from hexapod.simulator import Simulator
from pureples.hyperneat import create_phenotype_network
from pureples.shared import Substrate, run_hyper
from pureples.shared.visualize import draw_net
from neat.reporting import ReporterSet
import pymap_elites.map_elites.common as cm
import pymap_elites.map_elites.cvt as cvt_map_elites

"""
A script to produce the HyperNEAT maps

The script takes two command line arguments:
1) The size of the map to be tested
2) The run/map number
"""

# Fitness function that returns fitness and behavioural descriptor
def evaluate_gait(x, duration=5):
    cppn = neat.nn.FeedForwardNetwork.create(x, CONFIG)
    # Create ANN from CPPN and Substrate
    net = create_phenotype_network(cppn, SUBSTRATE)
    # Reset net

    leg_params = np.array(stationary).reshape(6, 5)
    try:
        controller = Controller(leg_params, body_height=0.15, velocity=0.5, period=1.0, crab_angle=-np.pi / 6,
                                ann=net)
    except:
        return 0, np.zeros(6)
    # Initialise Simulator
    simulator = Simulator(controller=controller, visualiser=False, collision_fatal=True)
    # Step in simulator
    contact_sequence = np.full((6, 0), False)
    for t in np.arange(0, duration, step=simulator.dt):
        try:
            simulator.step()
        except RuntimeError as collision:
            fitness = 0, np.zeros(6)
        contact_sequence = np.append(contact_sequence, simulator.supporting_legs().reshape(-1, 1), axis=1)
    fitness = simulator.base_pos()[0]  # distance travelled along x axis
    descriptor = np.nan_to_num(np.sum(contact_sequence, axis=1) / np.size(contact_sequence, axis=1), nan=0.0,
                               posinf=0.0, neginf=0.0)
    # Terminate Simulator
    simulator.terminate()
    # print(difference)
    # fitness = difference
    # Assign fitness to genome
    x.fitness = fitness
    return fitness, descriptor

# Setup Substrate
INPUT_COORDINATES = [(-0.6, 0.5), (-0.4, 0.5), (-0.2, 0.5),
                     (0.2, 0.5), (0.4, 0.5), (0.6, 0.5),
                     (0.2, 0), (0.4, 0), (0.6, 0),
                     (0.2, -0.5), (0.4, -0.5), (0.6, -0.5),
                     (-0.6, -0.5), (-0.4, -0.5), (-0.2, -0.5),
                     (-0.6, 0), (-0.4, 0), (-0.2, 0),
                     (0, 0.25), (0, -0.25)]
OUTPUT_COORDINATES = [(-0.6, 0.5), (-0.4, 0.5), (-0.2, 0.5),
                     (0.2, 0.5), (0.4, 0.5), (0.6, 0.5),
                     (0.2, 0), (0.4, 0), (0.6, 0),
                     (0.2, -0.5), (0.4, -0.5), (0.6, -0.5),
                     (-0.6, -0.5), (-0.4, -0.5), (-0.2, -0.5),
                     (-0.6, 0), (-0.4, 0), (-0.2, 0),]
HIDDEN_COORDINATES = [[(-0.6, 0.5), (-0.4, 0.5), (-0.2, 0.5),
                     (0.2, 0.5), (0.4, 0.5), (0.6, 0.5),
                     (0.2, 0), (0.4, 0), (0.6, 0),
                     (0.2, -0.5), (0.4, -0.5), (0.6, -0.5),
                     (-0.6, -0.5), (-0.4, -0.5), (-0.2, -0.5),
                     (-0.6, 0), (-0.4, 0), (-0.2, 0)]]

# Pass configuration to substrate
SUBSTRATE = Substrate(
    INPUT_COORDINATES, OUTPUT_COORDINATES, HIDDEN_COORDINATES)
ACTIVATIONS = len(HIDDEN_COORDINATES) + 2

# Configure cppn using config file
CONFIG = neat.config.Config(neat.genome.DefaultGenome, neat.reproduction.DefaultReproduction,
                            neat.species.DefaultSpeciesSet, neat.stagnation.DefaultStagnation,
                            'NEATHex/config-cppn')

# Method to load in initial high performing genomes
def load_genomes(num=200):
    reporters = ReporterSet()
    config = CONFIG
    stagnation = config.stagnation_type(config.stagnation_config, reporters)
    reproduction = config.reproduction_type(config.reproduction_config, reporters, stagnation)

    genomes = reproduction.create_new(config.genome_type, config.genome_config, num)
    print(type(genomes))
    print(type(list(genomes.values())))
    return list(genomes.values())


if __name__ == '__main__':
    mapSize = int(sys.argv[1])
    runNum = (sys.argv[2])
    # Map Elites paramters
    params = \
        {
            # more of this -> higher-quality CVT
            "cvt_samples": 1000000,
            # we evaluate in batches to parallelise
            "batch_size": 2390,
            # proportion of niches to be filled before starting (400)
            "random_init": 0.01,
            # batch for random initialization
            "random_init_batch": 200,
            # when to write results (one generation = one batch)
            "dump_period": 1e6,   # Change that
            # do we use several cores?
            "parallel": True,
            # do we cache the result of CVT and reuse?
            "cvt_use_cache": True,
            # min/max of parameters
            "min": 0,
            "max": 1,
        }

    # Used when starting from seeded genomes.
    # genomes = load_genomes(int (mapSize * 0.01))

    # Used when loading in checkpointed values
    filename = 'mapElitesOutput/HyperNEAT/'+ runNum+'_80000archive/archive_genome6002090.pkl'
    archive_load_file_name = 'mapElitesOutput/HyperNEAT/'+runNum+'_80000archive/archive6002090.dat'
    with open(filename, 'rb') as f:
        genomes = pickle.load(f)
        print(len(genomes))

    if not os.path.exists("mapElitesOutput/HyperNEAT/" + runNum + "_" + str(mapSize)):
        os.mkdir("mapElitesOutput/HyperNEAT/" + runNum + "_" + str(mapSize))
    if not os.path.exists("mapElitesOutput/HyperNEAT/" + runNum + "_" + str(mapSize) + "archive"):
        os.mkdir("mapElitesOutput/HyperNEAT/" + runNum + "_" + str(mapSize) + "archive")

 #   Used when initially loading in
 #    archive = cvt_map_elites.compute(6, genomes, evaluate_gait, n_niches = mapSize, max_evals=6e6,
 #                             log_file=open('mapElitesOutput/HyperNEAT/' + runNum + "_" + str(mapSize) + '/log.dat', 'w'), archive_file='mapElitesOutput/HyperNEAT/' + runNum + "_" + str(mapSize) + "archive" + '/archive',
 #                             params=params, variation_operator=cm.neatMutation)

    # Used when loading from archived files
    archive = cvt_map_elites.compute(6, genomes, evaluate_gait, n_niches=mapSize, max_evals=10e6,
                                     log_file=open('mapElitesOutput/HyperNEAT/' + runNum + "_" + str(mapSize) + '/log.dat', 'a'), archive_file='mapElitesOutput/HyperNEAT/' + runNum + "_" + str(mapSize) + "archive" + '/archive',
                                     archive_load_file=archive_load_file_name, params=params, start_index=6002090,
                                     variation_operator=cm.neatMutation)