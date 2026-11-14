#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# running vms
run_name=$1
clients=$2
infra=$3

# Check if running with CGPU
if [ "$infra" == "--gpu" ]; then
  echo "Running Evaluation with H100 GPU VM"
else
  echo "Running Evaluation with CPU VM"
  infra=""
fi

workspace_dir="${PWD}/../../workspace-$run_name"
echo in workspace $workspace_dir, running data sanitization exclave for $clients clients.

# for each client
for i in $(seq 1 $clients)
do
  # run data sanitization exclave
  echo running data sanitization exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/data-sanitization/measure-image"
  pushd .
  cd $exclave_workspace_dir
  # set env
  source ./set-env.sh
  # run
  ./remote-start.sh $infra > log.txt 2>&1 &
  popd

  sleep 2

done