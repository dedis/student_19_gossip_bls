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
    ('round_wall_sum', 'time until signature (sec)', 'protocol duration', 1, False),
    ('bandwidth_msg_tx_sum', 'messages sent per active node', 'message count', 1, True),
    ('bandwidth_tx_sum', 'data sent per active node (kB)', 'data transferred', 0.001, True),
]


def analysis_1():
    ref = parse('simulations_ref_1', check_sanity=False)
    new = parse('simulations_new_1', can_differ=['hosts', 'failingleaves'])
    ref_failing = ref.failingleafs + ref.failingsubleaders

    assert (ref.hosts == new.hosts).all()
    assert (ref_failing == new.failingleaves).all()
    assert (ref.mindelay == new.mindelay).all()
    assert (ref.maxdelay == new.maxdelay).all()
    assert (ref.rounds == 1).all()
    assert (new.rounds == 1).all()

    sizes = ref.hosts.unique()

    ref_cleaned = ref[~ref.round_wall_avg.isnull()]
    palette = sns.color_palette(n_colors=2)
    for num_nodes in sizes:
        ref_part_all = ref[ref.hosts == num_nodes]
        new_part = new[new.hosts == num_nodes]
        ref_failure = ref_part_all.round_wall_avg.isnull()
        new_failure = new_part.round_wall_avg.isnull()
        ref_part_failing = ref_part_all.failingleafs + ref_part_all.failingsubleaders

        _, ax = plt.subplots()
        sns.barplot(ref_part_failing, ref_failure, color='red', ci=68, capsize=.2)
        plt.title(f'Old protocol: rates of total protocol failure ($n={num_nodes}$)')
        plt.xlabel('failing nodes')
        plt.ylabel('protocol failure rate')
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: format(y, '.0%')))
        save_fig(f'failures_{num_nodes}', 1)

        ref_part = ref_cleaned[ref_cleaned.hosts == num_nodes]
        ref_part_failing = ref_part.failingleafs + ref_part.failingsubleaders

        for metric, label, title, factor, per_node in METRICS:
            _, ax = plt.subplots()

            # Workaround for legend colors
            sns.stripplot(ref_part_failing, ref_part[metric], size=5, palette=palette)
            handles, _, _, _ = matplotlib.legend._parse_legend_args([ax], ['', ''])
            ax.clear()
            ax.legend(handles, ['gossip protocol instance', 'old protocol instance'])

            if per_node:
                num_working = ref_part.hosts - ref_part_failing
                factor_adj = factor / num_working
            else:
                factor_adj = factor
            sns.stripplot(ref_part_failing, extract(ref_part, metric, factor_adj, False), size=3, color=palette[1])
            sns.stripplot(new_part.failingleaves, extract(new_part, metric, factor, per_node), size=3, color=palette[0])
            plt.title(f'Comparison of {title} ($n={num_nodes}$)')
            plt.xlabel('failing nodes')
            plt.ylabel(label)
            save_fig(f'{metric}_{num_nodes}', 1)

        for metric, label, title, factor, per_node in METRICS[:1]:
            _, ax = plt.subplots()

            # Workaround for legend colors
            sns.stripplot(ref_part_failing, ref_part[metric], size=5, palette=palette)
            handles, _, _, _ = matplotlib.legend._parse_legend_args([ax], ['', ''])
            ax.clear()
            ax.legend(handles, ['gossip protocol instance', 'old protocol instance'])

            if per_node:
                num_working = ref_part.hosts - ref_part_failing
                factor_adj = factor / num_working
            else:
                factor_adj = factor
            sns.stripplot(ref_part_failing, extract(ref_part, metric, factor_adj, False), size=3, color=palette[1])
            sns.stripplot(new_part.failingleaves, extract(new_part, metric, factor, per_node), size=3, color=palette[0])
            plt.title(f'Comparison of {title} ($n={num_nodes}$)')
            plt.xlabel('failing nodes')
            plt.ylabel(label)
            save_fig(f'{metric}_zoomed_{num_nodes}', 1, ylim=(0, 1.4))


def analysis_2():
    results = parse('simulations_2', can_differ=['failingleaves', 'delay'])
    num_nodes = results.hosts[0]
    delay = (results.mindelay + results.maxdelay) / 2
    hue = [f'{f} failing nodes' for f in results.failingleaves]
    for metric, label, title, factor, per_node in METRICS:
        plt.subplots()
        sns.lineplot(delay, extract(results, metric, factor, per_node), hue)
        plt.xlabel('message delay (sec)')
        plt.ylabel(label)
        plt.title(f'Mean {title} vs. message delay ($n={num_nodes}$)')
        save_fig(f'{metric}_by_delay', 2)


def analysis_3():
    results = parse('simulations_3', can_differ=['failingleaves'])
    num_nodes = results.hosts[0]
    for metric, label, title, factor, per_node in METRICS:
        plt.subplots()
        sns.scatterplot(results.failingleaves, extract(results, metric, factor, per_node))
        plt.xlabel('failing nodes')
        plt.ylabel(label)
        plt.title(f'Mean {title} vs. number of failing nodes ($n={num_nodes}$)')
        save_fig(f'{metric}_by_failing', 3)


def analysis_4():
    results = parse('simulations_4', can_differ=['hosts'])
    hue = ['tree-based aggregation' if tm else 'no early aggregation' for tm in results.treemode]
    for metric, label, title, factor, per_node in METRICS:
        plt.subplots()
        sns.lineplot(results.hosts, extract(results, metric, factor, per_node), hue)
        plt.xlabel('nodes')
        plt.ylabel(label)
        plt.title(f'Mean {title} vs. number of nodes (no failing nodes)')
        save_fig(f'{metric}_by_mode', 4)


def analysis_5():
    results = parse('simulations_5', can_differ=['hosts', 'delay'])
    delay = (results.mindelay + results.maxdelay) / 2
    hue = [f'mean message delay: {d}s' for d in delay]
    for metric, label, title, factor, per_node in METRICS:
        plt.subplots()
        sns.lineplot(results.hosts, extract(results, metric, factor, per_node), hue)
        plt.xlabel('nodes')
        plt.ylabel(label)
        plt.title(f'Mean {title} vs. number of nodes (no failing nodes)')
        save_fig(f'{metric}_by_num_nodes', 5)


def analysis_6():
    results = parse('simulations_6', can_differ=['gossiptick', 'failingleaves'])
    num_nodes = results.hosts[0]
    hue = [f'{f} failing nodes' for f in results.failingleaves]
    for metric, label, title, factor, per_node in METRICS:
        plt.subplots()
        sns.lineplot(results.gossiptick, extract(results, metric, factor, per_node), hue)
        plt.xlabel('gossip tick (sec)')
        plt.ylabel(label)
        plt.title(f'Mean {title} vs. gossip tick ($n={num_nodes}$)')
        save_fig(f'{metric}_by_gossip_tick', 6)


def analysis_7():
    results = parse('simulations_7', can_differ=['rumorpeers', 'failingleaves'])
    num_nodes = results.hosts[0]
    hue = [f'{f} failing nodes' for f in results.failingleaves]
    for metric, label, title, factor, per_node in METRICS:
        plt.subplots()
        sns.scatterplot(results.rumorpeers, extract(results, metric, factor, per_node), hue)
        plt.xlabel('rumor targets')
        plt.ylabel(label)
        plt.title(f'Mean {title} vs. number of rumor targets ($n={num_nodes}$)')
        save_fig(f'{metric}_by_rumor_targets', 7)


def analysis_8():
    results = parse('simulations_8', can_differ=['shutdownpeers', 'failingleaves'])
    num_nodes = results.hosts[0]
    hue = [f'{f} failing nodes' for f in results.failingleaves]
    for metric, label, title, factor, per_node in METRICS:
        plt.subplots()
        sns.scatterplot(results.shutdownpeers, extract(results, metric, factor, per_node), hue)
        plt.xlabel('shutdown targets')
        plt.ylabel(label)
        plt.title(f'Mean {title} vs. number of shutdown targets ($n={num_nodes}$)')
        save_fig(f'{metric}_by_shutdown_targets', 8)


def analysis_9():
    results = parse('simulations_9', can_differ=['gossiptick', 'rumorpeers', 'failingleaves'])
    num_nodes = results.hosts[0]
    hue = [f'{f} failing nodes' for f in results.failingleaves]
    for metric, label, title, factor, per_node in METRICS:
        plt.subplots()
        sns.scatterplot(results.rumorpeers, extract(results, metric, factor, per_node), hue)
        plt.xlabel('rumor targets')
        plt.ylabel(label)
        plt.title(f'Mean {title} vs. number of rumor targets\n(gossip tick adjusted to keep messages per node per second\nconstant) ($n={num_nodes}$)')
        save_fig(f'{metric}_by_rumor_targets', 9)


def analysis_10():
    results = parse('simulations_10', can_differ=['delay', 'failingleaves'])
    num_nodes = results.hosts[0]
    delays = (results.mindelay + results.maxdelay) / 2
    delay = delays[0]
    assert (delays - delay < 0.000001).all()
    delay_interval = results.maxdelay - results.mindelay
    hue = [f'{f} failing nodes' for f in results.failingleaves]
    for metric, label, title, factor, per_node in METRICS:
        plt.subplots()
        sns.lineplot(delay_interval, extract(results, metric, factor, per_node), hue)
        plt.xlabel('message delay range')
        plt.ylabel(label)
        plt.title(f'Mean {title} vs. message delay range\n(mean message delay is always {delay}s) ($n={num_nodes}$)')
        save_fig(f'{metric}_by_delay_range', 10)


def sanity_checks(results, can_differ=(), treemode=None, check_failures=True):
    attributes = {'rounds', 'hosts', 'failingleaves', 'maxdelay', 'mindelay',
                  'gossiptick', 'rumorpeers', 'shutdownpeers'}

    if 'delay' in can_differ:
        check = attributes.remove('maxdelay')
        check = attributes.remove('mindelay')
    check = attributes.difference(can_differ)

    assert not results.empty

    for attribute in check:
        assert (results[attribute] == results[attribute][0]).all(), attribute

    if treemode is not None:
        assert (results.treemode == treemode).all()

    if check_failures:
        assert not results.round_wall_avg.isnull().any()
        assert (results.round_wall_sum != 0).all()
        assert (results.bandwidth_msg_tx_sum != 0).all()
        assert (results.bandwidth_tx_sum != 0).all()


def parse(name, check_sanity=True, **sanity_kwargs):
    path = HERE / 'test_data' / (name + '.csv')
    results = pd.read_csv(path)
    if check_sanity:
        sanity_checks(results, **sanity_kwargs)
    return results


def extract(results, metric, factor, per_node):
    num_rounds = next(iter(results.rounds))
    if per_node:
        num_working = results.hosts - results.failingleaves
        factor /= num_working
    return results[metric] * factor / num_rounds


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
    analysis_1()
    analysis_2()
    analysis_3()
    analysis_4()
    analysis_5()
    analysis_6()
    analysis_7()
    analysis_8()
    analysis_9()
    analysis_10()


if __name__ == '__main__':
    main()
