#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

job_name=$1
min_clients=$2

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
ADMIN_NAME="admin@microsoft.com"
# start server
echo "STARTING SERVER"
${WORKSPACE}/${SERVER_NAME}/startup/start.sh &
sleep 120
echo "STARTING JOB SUBMIT"
# submit job
COMMAND="python3 ./submit_job.py --admin_dir=${WORKSPACE}/${ADMIN_NAME} --username=${ADMIN_NAME} --job=${JOB_DIR} --min_clients=${min_clients}"
echo "Running: ${COMMAND}"
eval "${COMMAND}" &
