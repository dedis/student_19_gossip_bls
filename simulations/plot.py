#!/usr/bin/env python3.7

"""Script to visualize the results."""


import csv
import pathlib

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns


HERE = pathlib.Path(__file__).resolve().parent

METRICS = [
    ('round_wall_sum', 'time until signature (s)', 'protocol duration', 1),
    ('bandwidth_msg_tx_sum', 'messages sent', 'message count', 1),
    ('bandwidth_tx_sum', 'data sent (kB)', 'data transferred', 0.001)
]


def analysis_1():
    ref = parse('simulations_ref_1')
    new = parse('simulations_new_1')
    ref_failing = ref.failingleafs + ref.failingsubleaders

    assert (new.gossiptick == new.gossiptick[0]).all()
    assert (new.rumorpeers == new.rumorpeers[0]).all()
    assert (new.shutdownpeers == new.shutdownpeers[0]).all()
    assert (new.treemode == new.treemode[0]).all()

    assert (ref.hosts == new.hosts).all()
    assert (ref_failing == new.failingleaves).all()
    assert (ref.mindelay == new.mindelay).all()
    assert (ref.maxdelay == new.maxdelay).all()
    assert (ref.rounds == 1).all()
    assert (new.rounds == 1).all()
    assert not new.round_wall_avg.isnull().any()
    assert (new.round_wall_sum != 0).all()
    assert (new.bandwidth_msg_tx_sum != 0).all()
    assert (new.bandwidth_tx_sum != 0).all()

    sizes = ref.hosts.unique()

    # Plot failure rates

    num_nodes = sizes[1]
    ref_part = ref[ref.hosts == num_nodes]
    new_part = new[new.hosts == num_nodes]
    ref_failure = ref_part.round_wall_avg.isnull()
    new_failure = new_part.round_wall_avg.isnull()
    ref_part_failing = ref_part.failingleafs + ref_part.failingsubleaders

    _, ax = plt.subplots()
    sns.barplot(ref_part_failing, ref_failure, color='red', ci=68, capsize=.2)
    plt.title(f'Old protocol: rates of total protocol failure ($n={num_nodes}$)')
    plt.xlabel('failing nodes')
    plt.ylabel('protocol failure rate')
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: format(y, '.0%')))
    save_fig('failures', 1)

    ref_cleaned = ref[~ref.round_wall_avg.isnull()]
    palette = sns.color_palette(n_colors=2)
    for num_nodes in sizes:
        ref_part = ref_cleaned[ref_cleaned.hosts == num_nodes]
        new_part = new[new.hosts == num_nodes]
        ref_part_failing = ref_part.failingleafs + ref_part.failingsubleaders

        for metric, label, title, factor in METRICS:
            _, ax = plt.subplots()

            # Workaround for legend colors
            sns.stripplot(ref_part_failing, ref_part[metric], size=5, palette=palette)
            handles, _, _, _ = matplotlib.legend._parse_legend_args([ax], ['', ''])
            ax.clear()
            ax.legend(handles, ['gossip protocol instance', 'old protocol instance'])

            sns.stripplot(ref_part_failing, ref_part[metric]*factor, size=3, color=palette[1])
            sns.stripplot(new_part.failingleaves, new_part[metric]*factor, size=3, color=palette[0])
            plt.title(f'Comparison of {title} ($n={num_nodes}$)')
            plt.xlabel('failing nodes')
            plt.ylabel(label)
            save_fig(f'{metric}_{num_nodes}', 1)


def analysis_2():
    results = parse('simulations_2')
    num_rounds = results.rounds[0]
    num_nodes = results.hosts[0]

    assert (results.rounds == num_rounds).all()
    assert (results.hosts == num_nodes).all()
    assert (results.gossiptick == results.gossiptick[0]).all()
    assert (results.rumorpeers == results.rumorpeers[0]).all()
    assert (results.shutdownpeers == results.shutdownpeers[0]).all()
    assert (results.treemode == results.treemode[0]).all()
    assert not results.round_wall_avg.isnull().any()
    assert (results.round_wall_sum != 0).all()
    assert (results.bandwidth_msg_tx_sum != 0).all()
    assert (results.bandwidth_tx_sum != 0).all()

    delay = (results.mindelay + results.maxdelay) / 2

    for metric, label, title, factor in METRICS:
        plt.subplots()
        sns.lineplot(delay, results[metric]*factor/num_rounds,
                     hue=[f'{f} failing nodes' for f in results.failingleaves])
        plt.xlabel('message delay (s)')
        plt.ylabel(label)
        plt.title(f'Average {title} vs. message delay ($n={num_nodes}$)')
        save_fig(f'{metric}_by_delay', 2)


def analysis_3():
    results = parse('simulations_3')
    num_rounds = results.rounds[0]
    num_nodes = results.hosts[0]

    assert (results.rounds == num_rounds).all()
    assert (results.hosts == num_nodes).all()
    assert (results.mindelay == results.mindelay[0]).all()
    assert (results.maxdelay == results.maxdelay[0]).all()
    assert (results.gossiptick == results.gossiptick[0]).all()
    assert (results.rumorpeers == results.rumorpeers[0]).all()
    assert (results.shutdownpeers == results.shutdownpeers[0]).all()
    assert (results.treemode == results.treemode[0]).all()
    assert not results.round_wall_avg.isnull().any()
    assert (results.round_wall_sum != 0).all()
    assert (results.bandwidth_msg_tx_sum != 0).all()
    assert (results.bandwidth_tx_sum != 0).all()

    for metric, label, title, factor in METRICS:
        plt.subplots()
        sns.scatterplot(results.failingleaves, results[metric]*factor/num_rounds)
        plt.xlabel('failing nodes')
        plt.ylabel(label)
        plt.title(f'Average {title} vs. number of failing nodes ($n={num_nodes}$)')
        save_fig(f'{metric}_by_failing', 3)


def analysis_4():
    results = parse('simulations_4')
    num_rounds = results.rounds[0]

    assert (results.rounds == num_rounds).all()
    assert (results.mindelay == results.mindelay[0]).all()
    assert (results.maxdelay == results.maxdelay[0]).all()
    assert (results.gossiptick == results.gossiptick[0]).all()
    assert (results.rumorpeers == results.rumorpeers[0]).all()
    assert (results.shutdownpeers == results.shutdownpeers[0]).all()
    assert not results.round_wall_avg.isnull().any()
    assert (results.round_wall_sum != 0).all()
    assert (results.bandwidth_msg_tx_sum != 0).all()
    assert (results.bandwidth_tx_sum != 0).all()

    for metric, label, title, factor in METRICS:
        plt.subplots()
        sns.lineplot(results.hosts, results[metric]*factor/num_rounds,
                     hue=['tree aggregation' if tm else 'no early aggregation' for tm in results.treemode])
        plt.xlabel('nodes')
        plt.ylabel(label)
        plt.title(f'Average {title} vs. number of nodes (no failing nodes)')
        save_fig(f'{metric}_by_mode', 4)


def analysis_5():
    results = parse('simulations_5')
    num_rounds = results.rounds[0]

    assert (results.rounds == num_rounds).all()
    assert (results.gossiptick == results.gossiptick[0]).all()
    assert (results.rumorpeers == results.rumorpeers[0]).all()
    assert (results.shutdownpeers == results.shutdownpeers[0]).all()
    assert (results.treemode == results.treemode[0]).all()
    assert not results.round_wall_avg.isnull().any()
    assert (results.round_wall_sum != 0).all()
    assert (results.bandwidth_msg_tx_sum != 0).all()
    assert (results.bandwidth_tx_sum != 0).all()

    delay = (results.mindelay + results.maxdelay) / 2

    for metric, label, title, factor in METRICS:
        plt.subplots()
        sns.lineplot(results.hosts, results[metric]*factor/num_rounds,
                     hue=[f'average message delay: {d}s' for d in delay])
        plt.xlabel('nodes')
        plt.ylabel(label)
        plt.title(f'Average {title} vs. number of nodes (no failing nodes)')
        save_fig(f'{metric}_by_num_nodes', 5)


def analysis_6():
    results = parse('simulations_6')
    num_rounds = results.rounds[0]
    num_nodes = results.hosts[0]

    assert (results.rounds == num_rounds).all()
    assert (results.hosts == num_nodes).all()
    assert (results.mindelay == results.mindelay[0]).all()
    assert (results.maxdelay == results.maxdelay[0]).all()
    assert (results.rumorpeers == results.rumorpeers[0]).all()
    assert (results.shutdownpeers == results.shutdownpeers[0]).all()
    assert (results.treemode == results.treemode[0]).all()
    assert not results.round_wall_avg.isnull().any()
    assert (results.round_wall_sum != 0).all()
    assert (results.bandwidth_msg_tx_sum != 0).all()
    assert (results.bandwidth_tx_sum != 0).all()

    delay = (results.mindelay + results.maxdelay) / 2

    for metric, label, title, factor in METRICS:
        plt.subplots()
        sns.lineplot(results.gossiptick, results[metric]*factor/num_rounds,
                     hue=[f'{f} failing nodes' for f in results.failingleaves])
        plt.xlabel('gossip tick (s)')
        plt.ylabel(label)
        plt.title(f'Average {title} vs. gossip tick ($n={num_nodes}$)')
        save_fig(f'{metric}_by_delay', 6)


def analysis_7():
    results = parse('simulations_7')
    num_rounds = results.rounds[0]
    num_nodes = results.hosts[0]

    assert (results.rounds == num_rounds).all()
    assert (results.hosts == num_nodes).all()
    assert (results.mindelay == results.mindelay[0]).all()
    assert (results.maxdelay == results.maxdelay[0]).all()
    assert (results.gossiptick == results.gossiptick[0]).all()
    assert (results.shutdownpeers == results.shutdownpeers[0]).all()
    assert (results.treemode == results.treemode[0]).all()
    assert not results.round_wall_avg.isnull().any()
    assert (results.round_wall_sum != 0).all()
    assert (results.bandwidth_msg_tx_sum != 0).all()
    assert (results.bandwidth_tx_sum != 0).all()

    delay = (results.mindelay + results.maxdelay) / 2

    for metric, label, title, factor in METRICS:
        plt.subplots()
        sns.scatterplot(results.rumorpeers, results[metric]*factor/num_rounds,
                        hue=[f'{f} failing nodes' for f in results.failingleaves])
        plt.xlabel('rumor targets')
        plt.ylabel(label)
        plt.title(f'Average {title} vs. number of rumor targets ($n={num_nodes}$)')
        save_fig(f'{metric}_by_delay', 7)


def analysis_8():
    results = parse('simulations_8')
    num_rounds = results.rounds[0]
    num_nodes = results.hosts[0]

    assert (results.rounds == num_rounds).all()
    assert (results.hosts == num_nodes).all()
    assert (results.mindelay == results.mindelay[0]).all()
    assert (results.maxdelay == results.maxdelay[0]).all()
    assert (results.gossiptick == results.gossiptick[0]).all()
    assert (results.rumorpeers == results.rumorpeers[0]).all()
    assert (results.treemode == results.treemode[0]).all()
    assert not results.round_wall_avg.isnull().any()
    assert (results.round_wall_sum != 0).all()
    assert (results.bandwidth_msg_tx_sum != 0).all()
    assert (results.bandwidth_tx_sum != 0).all()

    delay = (results.mindelay + results.maxdelay) / 2

    for metric, label, title, factor in METRICS:
        plt.subplots()
        sns.scatterplot(results.shutdownpeers, results[metric]*factor/num_rounds,
                        hue=[f'{f} failing nodes' for f in results.failingleaves])
        plt.xlabel('shutdown targets')
        plt.ylabel(label)
        plt.title(f'Average {title} vs. number of shutdown targets ($n={num_nodes}$)')
        save_fig(f'{metric}_by_delay', 8)


def analysis_9():
    results = parse('simulations_9')
    num_rounds = results.rounds[0]
    num_nodes = results.hosts[0]

    assert (results.rounds == num_rounds).all()
    assert (results.hosts == num_nodes).all()
    assert (results.mindelay == results.mindelay[0]).all()
    assert (results.maxdelay == results.maxdelay[0]).all()
    assert (results.shutdownpeers == results.shutdownpeers[0]).all()
    assert (results.treemode == results.treemode[0]).all()
    assert not results.round_wall_avg.isnull().any()
    assert (results.round_wall_sum != 0).all()
    assert (results.bandwidth_msg_tx_sum != 0).all()
    assert (results.bandwidth_tx_sum != 0).all()

    delay = (results.mindelay + results.maxdelay) / 2

    for metric, label, title, factor in METRICS:
        plt.subplots()
        sns.scatterplot(results.rumorpeers, results[metric]*factor/num_rounds,
                        hue=[f'{f} failing nodes' for f in results.failingleaves])
        plt.xlabel('rumor targets')
        plt.ylabel(label)
        plt.title(f'Average {title} vs. number of rumor targets\n(gossip tick adjusted to keep messages per node per second\nconstant) ($n={num_nodes}$)')
        save_fig(f'{metric}_by_delay', 9)


def parse(name):
    path = HERE / 'test_data' / (name + '.csv')
    return pd.read_csv(path)


def save_fig(name, analysis, tight_layout=True, ylim=(0, None), close=True):
    path = HERE / 'figures' / str(analysis) / (name + '.png')
    plt.ylim(ylim)
    if tight_layout:
        plt.tight_layout()
    plt.savefig(path)
    if close:
        plt.close()


def main():
    sns.set_style('whitegrid')
    sns.set_context('notebook')
    analysis_2();return

    analysis_1()
    analysis_2()
    analysis_3()
    analysis_4()
    analysis_5()
    analysis_6()
    analysis_7()
    analysis_8()
    analysis_9()


if __name__ == '__main__':
    main()
