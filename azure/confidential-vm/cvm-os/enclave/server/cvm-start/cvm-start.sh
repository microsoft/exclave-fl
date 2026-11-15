#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# settings: azure/config.env, which the image keeps (MAA_ENDPOINT, IMAGESERVER)
source /home/workspace/exclave-fl/azure/load-config.sh || exit 1

job_name=$1
min_clients=$2

# load docker image
pushd .
echo [!] loading docker image...
cd /home/workspace/sidecar_image
docker load -i cvm-enclave-server-proxy.tar
popd

# load env var for proxy
: "${MAA_ENDPOINT:?missing from azure/config.env}"
export ATTESTATION_POLICY=$(cat /home/workspace/attestation_policy.json | base64 -w0) 

# config and run proxy
pushd .
echo [!] running fl server...
cd /home/workspace/exclave-fl/azure/confidential-vm/proxy/enclave-proxy/server/workspace
./iptable.sh
./start-docker.sh &
popd

# run nvflare and submit job
cd /home/workspace/exclave-fl/nvflare-ext/examples/evaluation
# activate venv
source /home/workspace/env/bin/activate
# add current folder to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}"
echo "PYTHONPATH is ${PYTHONPATH}"
WORKSPACE="${PWD}/secure_workspace"
JOB_DIR="${PWD}/job/${job_name}"
SERVER_NAME="server"
ADMIN_NAME="admin"
# start server
echo "STARTING SERVER"
${WORKSPACE}/${SERVER_NAME}/startup/nvflare_start.sh &
sleep 120
echo "STARTING JOB SUBMIT"
# submit job
COMMAND="python3 ./submit_job.py --admin_dir=${WORKSPACE}/${ADMIN_NAME} --username=${ADMIN_NAME} --job=${JOB_DIR} --min_clients=${min_clients} --poc"
echo "Running: ${COMMAND}"
eval "${COMMAND}" &

