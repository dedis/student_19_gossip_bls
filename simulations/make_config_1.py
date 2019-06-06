#!/usr/bin/env python3

"""Script to make a config file."""


import pathlib
import random
import sys

random.seed(42)


# `HERE` is the directory this script is located in.
HERE = pathlib.Path(__file__).resolve().parent
CONFIG_PATH_REF = HERE / 'simulations_ref_1.toml'
CONFIG_PATH_NEW = HERE / 'simulations_new_1.toml'

ROUNDS = 25
MIN_DELAY = 0.095
MAX_DELAY = 0.105
GOSSIP_TICK = 0.07
RUMOR_PEERS = 3
SHUTDOWN_PEERS = 2
TREE_MODE = 1


def print_toml(filename, protocol, new=False):
    with open(filename, 'w') as dest:
        print(f'Simulation = "{protocol}"', file=dest)
        print('Servers = 1', file=dest)
        bf = 200 if new else 1
        print('Bf =', bf, file=dest)
        print('Rounds = 1', file=dest)
        print('RunWait = "600s"', file=dest)
        print('Suite = "bn256.adapter"', file=dest)
        print(file=dest)
        if new:
            print('Hosts, FailingLeaves, MinDelay, MaxDelay, GossipTick, '
                  'RumorPeers, ShutdownPeers, TreeMode', file=dest)
        else:
            print('Hosts, NSubtrees, FailingSubleaders, FailingLeafs, MinDelay, '
                  'MaxDelay', file=dest)

        for num_nodes in 7, 16, 25, 36:
            max_failures = (num_nodes-1)//3
            for num_failing in range(max_failures + 1):
                for _ in range(ROUNDS):
                    if new:
                        values = (num_nodes, num_failing, MIN_DELAY, MAX_DELAY,
                                  GOSSIP_TICK, RUMOR_PEERS, SHUTDOWN_PEERS,
                                  TREE_MODE)
                    else:
                        subtrees = int((num_nodes - 1)**0.5)
                        num_leaves = num_nodes - subtrees - 1
                        population = [1] * subtrees + [0] * num_leaves
                        f_subl = sum(random.sample(population, num_failing))
                        f_leaves = num_failing - f_subl
                        values = (num_nodes, subtrees, f_subl, f_leaves,
                                  MIN_DELAY, MAX_DELAY)
                    print(', '.join(str(v) for v in values), file=dest)



def main():
    print_toml(CONFIG_PATH_REF, 'BlsCosiProtocol')
    print_toml(CONFIG_PATH_NEW, 'BlsCosiBundleProtocol', new=True)


if __name__ == '__main__':
    main()
