#!/usr/bin/env python3

"""Script to make a config file."""


import pathlib
import random
import sys

random.seed(42)


# `HERE` is the directory this script is located in.
HERE = pathlib.Path(__file__).resolve().parent
CONFIG_PATH = HERE / 'simulations_ref_1.toml'

ROUNDS = 1
DELAY = 0.1

def main():
    with open(CONFIG_PATH, 'w') as dest:
        print('Simulation = "BlsCosiProtocol"', file=dest)
        print('Servers = 1', file=dest)
        print('Bf = 1', file=dest)
        print('Rounds = 1', file=dest)
        print('RunWait = "600s"', file=dest)
        print('Suite = "bn256.adapter"', file=dest)
        print(file=dest)
        print('Hosts, NSubtrees, FailingSubleaders, FailingLeafs, MinDelay, MaxDelay', file=dest)

        for num_nodes in range(4, 26):
            for num_failing in 0, 2, 4:
                subtrees = int((num_nodes - 1)**0.5)
                num_leaves = num_nodes - subtrees - 1
                population = [1] * subtrees + [0] * num_leaves
                if num_failing > len(population):
                    continue
                for _ in range(ROUNDS):
                    f_subl = sum(random.sample(population, num_failing))
                    f_leaves = num_failing - f_subl
                    values = num_nodes, subtrees, f_subl, f_leaves, DELAY, DELAY
                    print(', '.join(str(v) for v in values), file=dest)


if __name__ == '__main__':
    main()
