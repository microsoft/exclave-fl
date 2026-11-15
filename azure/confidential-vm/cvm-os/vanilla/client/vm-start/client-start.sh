#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

CLIENT_ID=$1
INFRA=$2

# config and mount the data disk
pushd .
cd /home/workspace/exclave-fl/azure/confidential-vm/storage/open-disk
if [ "$INFRA" == "--gpu" ]; then
	umount /dev/sdb1
	./vanilla-open.sh --gpu
else
	./vanilla-open.sh
fi
popd

# start running nvflare client
cd /home/workspace/exclave-fl/nvflare-ext/examples/evaluation
source /home/workspace/env/bin/activate
echo [!] running nvflare client...
# add current folder to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}"
echo "PYTHONPATH is ${PYTHONPATH}"
workspace="${PWD}/secure_workspace"
site_name="site-${CLIENT_ID}"
${workspace}/${site_name}/startup/start.sh &
