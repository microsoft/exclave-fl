#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# settings: azure/config.env, which the image keeps (MAA_ENDPOINT, IMAGESERVER)
source /home/workspace/exclave-fl/azure/load-config.sh || exit 1

CLIENT_ID=$1

# load docker image
pushd .
echo [!] loading docker images...
cd /home/workspace/sidecar_image
docker load -i cvm-exclave-client-proxy.tar
popd

# base64 of an empty JSON object
export ATTESTATION_POLICY="ewp9"

# config and run proxy
: "${MAA_ENDPOINT:?missing from azure/config.env}"
pushd .
echo [!] start proxy...
cd /home/workspace/exclave-fl/azure/confidential-vm/proxy/exclave-proxy/client/workspace
./iptable.sh
./start-docker.sh &
popd

# start running nvflare client
cd /home/workspace/exclave-fl/nvflare-ext/examples/evaluation
# activate venv
source /home/workspace/env/bin/activate
echo [!] running nvflare client...
# add current folder to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}"
echo "PYTHONPATH is ${PYTHONPATH}"
workspace="${PWD}/secure_workspace"
site_name="site-${CLIENT_ID}"
${workspace}/${site_name}/startup/nvflare_start.sh &
