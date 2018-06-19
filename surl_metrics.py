#!/usr/bin/env python3

import argparse
import collections
import datetime
import os
import requests
import sys
import tabulate


import surl


DEFAULT_HEADERS = {
    'Accept': 'application/json, application/hal+json',
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache',
}


def get_snap_id(snap_name, config):
    headers = surl.DEFAULT_HEADERS.copy()
    headers['Authorization'] = surl.get_authorization_header(
        config.root, config.discharge)

    url = '{}/dev/api/snaps/info/{}'.format(
        surl.CONSTANTS[config.store_env]['sca_base_url'], snap_name)
    r = requests.get(url=url, headers=headers)
    r.raise_for_status()
    return r.json()['snap_id']


def get_publisher_metric(snap_id, metric_name, config):
    headers = surl.DEFAULT_HEADERS.copy()
    headers['Authorization'] = surl.get_authorization_header(
        config.root, config.discharge)

    yesterday = datetime.datetime.utcnow().date() - datetime.timedelta(1)

    start = end = yesterday.isoformat()
    filters = [
        {"metric_name": metric_name, "snap_id": snap_id,
         "start": start, "end": end}
    ]

    url = '{}/dev/api/snaps/metrics'.format(
        surl.CONSTANTS[config.store_env]['sca_base_url'])

    payload = {"filters": filters}
    r = requests.post(url=url, json=payload, headers=headers)
    r.raise_for_status()
    return r.json()['metrics']


def get_public_metric(snap_id, metric_name, config):
    headers = surl.DEFAULT_HEADERS.copy()
    headers['X-Ubuntu-Series'] = '16'

    yesterday = datetime.datetime.utcnow().date() - datetime.timedelta(1)
    start = end = yesterday.isoformat()
    filters = [
        {"metric_name": metric_name, "snap_id": snap_id,
         "start": start, "end": end}
    ]

    url = '{}/api/v1/snaps/metrics'.format(
        surl.CONSTANTS[config.store_env]['api_base_url'])
    payload = filters
    r = requests.post(url=url, json=payload, headers=headers)
    r.raise_for_status()
    return {m['name']: m['values'][0] for m in r.json()[0]['series']}


METRICS = (
    'weekly_installed_base_by_channel',
    'weekly_installed_base_by_operating_system',
    'weekly_installed_base_by_version',
)


def main():
    auth_dir = os.path.abspath(os.environ.get('SNAP_USER_COMMON', '.'))

    parser = argparse.ArgumentParser(
        description='Snap store metrics viewer ...'
    )

    try:
        config, remainder = surl.get_config_from_cli(parser, auth_dir)
    except surl.CliError as e:
        print(e)
        return 1
    except surl.CliDone:
        return 0

    parser.add_argument('-v', '--debug', action='store_true',
                        help='Prints request and response headers')

    parser.add_argument('snap_name')

    parser.add_argument('metric', choices=METRICS)

    args = parser.parse_args(remainder)

    if args.debug:
        # # The http.client logger pollutes stdout.
        # from http.client import HTTPConnection
        # HTTPConnection.debuglevel = 1
        import logging
        handler = requests.packages.urllib3.add_stderr_logger()
        handler.setFormatter(logging.Formatter('\033[1m%(message)s\033[0m'))

    if not args.snap_name:
        args.snap_name = 'lxd'

    print('Resolving snap_id for {} ...'.format(args.snap_name))

    snap_id = get_snap_id(args.snap_name, config)

    print('Collecting publisher metrics for {} ...'.format(snap_id))

    publisher_metrics = get_publisher_metric(snap_id, args.metric, config)

    by_terms = {
        m['name']: m['values'][0] for m in publisher_metrics[0]['series']}
    sorted_metric = collections.OrderedDict(
        sorted(by_terms.items(), key=lambda t: t[1] or -1, reverse=True))

    table = collections.OrderedDict([
        ('Terms', sorted_metric.keys()),
        ('Values', sorted_metric.values()),
    ])
    print(tabulate.tabulate(table, headers='keys'))


if __name__ == '__main__':
    sys.exit(main())
