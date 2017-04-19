#!/usr/bin/env python3
import os.path
import argparse
import yaml
import json
import requests
import tempfile

from _common import *


cl_parser = argparse.ArgumentParser(
    description='Create cluster instances'
)
cl_parser.add_argument('cluster_name', help='Specify the name of the cluster')
cl_parser.add_argument(
    'token', help='DigitalOcean token',
)
cl_parser.add_argument(
    'ssh_key_id', help='DigitalOcean SSH key ID',
)
args = cl_parser.parse_args()


def _call_do_api(path, method, data=None):
    url = 'https://api.digitalocean.com/v2/{}'.format(path)
    r = requests.request(
        method,
        url,
        json=data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(args.token),
        }
    )
    r.raise_for_status()
    return r.json()


def _get_from_do(path):
    return _call_do_api(path, 'GET')


def _post_to_do(path, data):
    return _call_do_api(path, 'POST', data=data)


def _create_instance(name, ignite_config, volume=None):
    full_name = '{}-{}'.format(args.cluster_name, name)
    if full_name in _existing_instances:
        info('Instance {} already exists - not creating'.format(full_name))
    else:
        info('Creating instance {}'.format(full_name))

        if ignite_config:
            with open('test.ign', 'wt') as f:
                f.write(
                    yaml.dump(ignite_config, default_flow_style=False) + '\n')
            with tempfile.NamedTemporaryFile(mode='wt') as f:
                f.write(yaml.dump(ignite_config, default_flow_style=False))
                f.flush()
                ignite_config_raw = subprocess.check_output([
                    'ct', '-in-file', f.name, '-platform', 'digitalocean',
                    '-strict',
                ]).decode()
                ignite_config_raw = ignite_config_raw.replace('"', '\\')
        else:
            ignite_config_raw = None

        data = {
            'region': 'fra1',
            'image': 'coreos-beta',
            'size': '512mb',
            'name': full_name,
            'private_networking': True,
            'ssh_keys': [args.ssh_key_id, ],
            'tags': [args.cluster_name, ],
            'user_data': ignite_config_raw,
        }
        if volume is not None:
            data['volumes'] = [volume['id'], ]
        _post_to_do('droplets', data)


_existing_instances = [d['name'] for d in _get_from_do('droplets')['droplets']]


# Create volumes
volumes = []
for i in range(2):
    volume_name = '{}{}'.format(args.cluster_name, i + 1)
    volumes_info = _get_from_do('volumes?region=fra1')['volumes']
    try:
        volume = next((v for v in volumes_info if v['name'] == volume_name))
    except StopIteration:
        info('Creating volume {}'.format(volume_name))
        resp = _post_to_do('volumes', {
            'size_gigabytes': 10,
            'name': volume_name,
            'region': 'fra1',
        })
        volumes.extend(resp['volume'])
    else:
        info('Volume {} already exists - not creating'.format(volume_name))
        volumes.append(volume)


_num_masters = 1
_num_existing_masters = len([
    i for i in range(_num_masters) if
    '{}-master{}'.format(args.cluster_name, i + 1) in _existing_instances
])
if _num_existing_masters < _num_masters:
    resp = requests.get('https://discovery.etcd.io/new?size={}'.format(
        _num_masters))
    resp.raise_for_status()
    etcd_discovery_url = resp.text
    # Create masters
    for i in range(_num_masters):
        ignite_config = {
            'etcd': {
                'name': '{HOSTNAME}',
                'initial_advertise_peer_urls': 'http://{PRIVATE_IPV4}:2380',
                'listen_peer_urls': 'http://{PRIVATE_IPV4}:2380',
                'listen_client_urls': 'http://0.0.0.0:2379',
                'advertise_client_urls': 'http://{PRIVATE_IPV4}:2379',
                'discovery': etcd_discovery_url,
            },
        }
        _create_instance(
            'master{}'.format(i + 1), ignite_config, volume=volumes[i]
        )
else:
    info('Master cluster already exists - not creating')


# Create workers
for i in range(2):
    ignite_config = {}
    _create_instance('worker{}'.format(i + 1), ignite_config)

info('Success!')
