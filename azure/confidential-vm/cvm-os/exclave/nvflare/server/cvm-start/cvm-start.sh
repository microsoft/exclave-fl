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
docker load -i cvm-exclave-server-proxy.tar
popd

# base64 of an empty JSON object
export ATTESTATION_POLICY="ewp9"

# config and run proxy
: "${MAA_ENDPOINT:?missing from azure/config.env}"
pushd .
echo [!] running fl server...
cd /home/workspace/exclave-fl/azure/confidential-vm/proxy/exclave-proxy/server/workspace
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

