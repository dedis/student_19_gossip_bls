#!/usr/bin/env python3

"""Script to vizaulize the results."""

import collections
import csv
import statistics

import matplotlib.pyplot as plt


def get_data(treemode):
    data_path = f'test_data/simulations_t_{treemode}.csv'

    with open(data_path) as file:
        timing_measurements = collections.defaultdict(list)
        messages_tx_measurements = collections.defaultdict(list)
        bytes_tx_measurements = collections.defaultdict(list)
        for record in csv.DictReader(file):
            assert record['rounds'] == '1'
            assert record['hosts'] == '20'
            assert record['failingleaves'] == '0'
            assert record['gossiptick'] == '0.1'
            assert record['rumorpeers'] == '2'
            assert record['shutdownpeers'] == '2'
            assert record['treemode'] == ('1' if treemode == 'on' else '0')
            assert record['mindelay'] == record['maxdelay']

            if record['round_wall_sum'] is None:
                continue
            delay = float(record['mindelay'])
            timing = float(record['round_wall_sum'])
            messages_tx = float(record['bandwidth_msg_tx_sum'])
            bytes_tx = float(record['bandwidth_tx_sum'])
            timing_measurements[delay].append(timing)
            messages_tx_measurements[delay].append(messages_tx)
            bytes_tx_measurements[delay].append(bytes_tx)

    delays = list(timing_measurements)
    timings = [statistics.mean(timings) for timings in timing_measurements.values()]
    messages_txs = [statistics.mean(messages_tx) for messages_tx in messages_tx_measurements.values()]
    bytes_txs = [statistics.mean(bytes_tx) for bytes_tx in bytes_tx_measurements.values()]

    return delays, timings, messages_txs, bytes_txs


def main():
    delays, timings, _, _ = get_data('on')
    plt.plot(delays, timings, label='treemode on')
    delays, timings, _, _  = get_data('off')
    plt.plot(delays, timings, label='treemode off')
    plt.legend()
    plt.title(f"20 nodes, no failures, gossip tick 0.1 s, 2 rumor peers, 2 shutdown peers, average out of 10 rounds")
    plt.xlabel('message delay (s)')
    plt.ylabel('time (s)')
    plt.show()

    delays, _, messages_txs, _ = get_data('on')
    plt.plot(delays, messages_txs, label='treemode on')
    delays, _, messages_txs, _  = get_data('off')
    plt.plot(delays, messages_txs, label='treemode off')
    plt.legend()
    plt.title(f"20 nodes, no failures, gossip tick 0.1 s, 2 rumor peers, 2 shutdown peers, average out of 10 rounds")
    plt.xlabel('message delay (s)')
    plt.ylabel('messages sent (number)')
    plt.show()

    delays, _, _, bytes_txs = get_data('on')
    plt.plot(delays, bytes_txs, label='treemode on')
    delays, _, _, bytes_txs  = get_data('off')
    plt.plot(delays, bytes_txs, label='treemode off')
    plt.legend()
    plt.title(f"20 nodes, no failures, gossip tick 0.1 s, 2 rumor peers, 2 shutdown peers, average out of 10 rounds")
    plt.xlabel('message delay (s)')
    plt.ylabel('bytes sent (number)')
    plt.show()



if __name__ == '__main__':
    main()
