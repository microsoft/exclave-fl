#!/usr/bin/env bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# run this script with sudo privilege

# settings: azure/config.env, which the image keeps (MAA_ENDPOINT, IMAGESERVER)
source /home/workspace/exclave-fl/azure/load-config.sh || exit 1

# load docker image
pushd .
echo [!] loading docker images...
cd /home/workspace/sidecar_image
docker load -i cvm-exclave-proxy.tar
popd

# load env var for proxy
: "${MAA_ENDPOINT:?missing from azure/config.env}"
# base64 of an empty JSON object
export ATTESTATION_POLICY="ewp9"

# config and run proxy
pushd .
echo [!] start proxy...
cd /home/workspace/exclave-fl/azure/confidential-vm/proxy/exclave-proxy/exclave/workspace
./iptable.sh
./start-docker.sh &
popd

# start aggregation exclave 
# activate venv
source /home/workspace/env/bin/activate
# add current folder to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}"
echo "PYTHONPATH is ${PYTHONPATH}"
python3 aggregation_exclave.py
