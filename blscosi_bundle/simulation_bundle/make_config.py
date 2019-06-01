#!/usr/bin/env python3

"""Script to make a config file."""


import pathlib
import sys


# `HERE` is the directory this script is located in.
HERE = pathlib.Path(__file__).resolve().parent
CONFIG_PATH = HERE / 'simulations.toml'
DATA_PATH = HERE / 'simulation_data.txt'

ROUNDS = 10


def main():
    if len(sys.argv) <= 1:
        data_path = DATA_PATH
    else:
        data_path = str(DATA_PATH).replace('.txt', f'_{sys.argv[1]}.txt')

    with open(CONFIG_PATH, 'w') as dest:
        print('Simulation = "BlsCosiBundleProtocol"', file=dest)
        print('Servers = 8', file=dest)
        print('Bf = 200', file=dest)
        print('Rounds = 1', file=dest)
        print('RunWait = "600s"', file=dest)
        print('Suite = "bn256.adapter"', file=dest)
        print(file=dest)

        with open(data_path) as source:
            print(source.readline(), file=dest, end='')    # Header
            for line in source:
                print(line * ROUNDS, file=dest, end='')


if __name__ == '__main__':
    main()
