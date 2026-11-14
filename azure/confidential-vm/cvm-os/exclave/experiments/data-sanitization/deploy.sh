#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# deploying vms
run_name=$1
clients=$2
infra=$3

# Check if running with CGPU
if [ "$infra" == "--gpu" ]; then
  echo "Deploying Evaluation with H100 GPU VM"
else
  echo "Deploying Evaluation with CPU VM"
  infra=""
fi

workspace_dir="${PWD}/../../workspace-$run_name"
echo running in workspace $workspace_dir, deploy data sanitization exclave for $clients clients.

# deploy data sanitization exclave
for i in $(seq 1 $clients)
do
  # deploy data sanitization exclave
  echo deploying data sanitization exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/data-sanitization/measure-image"
  pushd .
  cd $exclave_workspace_dir
  # set env
  source ./set-env.sh
  # deploy
  ./deploy-image.sh $infra 2>&1 &
  popd

  sleep 2

done