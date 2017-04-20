#!/usr/bin/env python3
import os.path
import argparse

from _common import *


cl_parser = argparse.ArgumentParser(
    description='Generate Kubernetes cluster certificates'
)
cl_parser.add_argument('master_ip', help='Specify master IP')
cl_parser.add_argument('worker_ips', help='Specify worker IPs')
cl_parser.add_argument(
    '-o', '--output', help='Specify output directory',
    default='.',
)
cl_parser.add_argument(
    '-f', '--force', action='store_true',
    help='Force overwriting of existing files', default=False,
)
args = cl_parser.parse_args()
force = args.force

CONF = {
    'masterIp': args.master_ip,
    'workerIps': [x.strip() for x in args.worker_ips.split(',')],
}

info('Generating cluster certificates...')
if not os.path.exists(args.output):
    os.makedirs(args.output)

os.chdir(args.output)


if not os.path.exists('ca-key.pem') or force:
    info('Generating cluster root CA')
    run_command(['openssl', 'genrsa', '-out', 'ca-key.pem', '2048', ])
    run_command([
        'openssl', 'req', '-x509', '-new', '-nodes', '-key', 'ca-key.pem',
        '-days', '10000', '-out', 'ca.pem', '-subj', '/CN=kube-ca'
    ])
else:
    info('Reusing cluster root CA')

if not os.path.exists('apiserver-key.pem') or force:
    info('Generating API server key pair')
    with open('openssl.cnf', 'wt') as f:
        f.write("""[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[req_distinguished_name]
[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names
[alt_names]
DNS.1 = kubernetes
DNS.2 = kubernetes.default
DNS.3 = kubernetes.default.svc
DNS.4 = kubernetes.default.svc.cluster.local
IP.1 = 10.3.0.1
IP.2 = {c[masterIp]}
""".format(c=CONF))
    run_command([
        'openssl', 'genrsa', '-out', 'apiserver-key.pem', '2048',
    ])
    run_command([
        'openssl', 'req', '-new', '-key', 'apiserver-key.pem', '-out',
        'apiserver.csr', '-subj', '/CN=kube-apiserver', '-config',
        'openssl.cnf',
    ])
    run_command([
        'openssl', 'x509', '-req', '-in', 'apiserver.csr', '-CA', 'ca.pem',
        '-CAkey', 'ca-key.pem', '-CAcreateserial', '-out', 'apiserver.pem',
        '-days', '365', '-extensions', 'v3_req', '-extfile', 'openssl.cnf',
    ])
else:
    info('Reusing API server key pair')

with open('worker-openssl.cnf', 'wt') as f:
    f.write("""[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[req_distinguished_name]
[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names
[alt_names]
IP.1 = $ENV::WORKER_IP
""")

for worker in range(0, 2):
    worker_name = 'worker{}'.format(worker + 1)
    if not os.path.exists('{}-key.pem'.format(worker_name)) or force:
        info('Generating worker {} key pair'.format(worker + 1))
        run_command([
            'openssl', 'genrsa', '-out', '{}-key.pem'.format(worker_name),
            '2048',
        ])
        run_command([
            'openssl', 'req', '-new', '-key', '{}-key.pem'.format(worker_name),
            '-out', '{}.csr'.format(worker_name), '-subj',
            '/CN={}'.format(worker_name), '-config', 'worker-openssl.cnf',
        ], env={'WORKER_IP': CONF['workerIps'][worker], })
        run_command([
            'openssl', 'x509', '-req', '-in', '{}.csr'.format(worker_name),
            '-CA', 'ca.pem', '-CAkey', 'ca-key.pem', '-CAcreateserial', '-out',
            '{}.pem'.format(worker_name), '-days', '365', '-extensions',
            'v3_req', '-extfile', 'worker-openssl.cnf',
        ], env={'WORKER_IP': CONF['workerIps'][worker], })
    else:
        info('Reusing worker {} key pair'.format(worker + 1))

if not os.path.exists('admin-key.pem'):
    info('Generating admin key pair')
    run_command([
        'openssl', 'genrsa', '-out', 'admin-key.pem', '2048',
    ])
    run_command([
        'openssl', 'req', '-new', '-key', 'admin-key.pem', '-out', 'admin.csr',
        '-subj', '/CN=kube-admin',
    ])
    run_command([
        'openssl', 'x509', '-req', '-in', 'admin.csr', '-CA', 'ca.pem',
        '-CAkey', 'ca-key.pem', '-CAcreateserial', '-out', 'admin.pem',
        '-days', '365',
    ])
else:
    info('Re-using admin key pair')

info('Success!')
