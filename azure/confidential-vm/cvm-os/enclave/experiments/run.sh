#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# running vms
run_name=$1
job_name=$2
clients=$3
infra=$4

# Check if running with CGPU
if [ "$infra" == "--gpu" ]; then
  echo "Running Evaluation with H100 GPU VM"
else
  echo "Running Evaluation with CPU VM"
  infra=""
fi

workspace_dir="${PWD}/../workspace-$run_name"
echo running in workspace $workspace_dir, with $clients clients

# for each client
for i in $(seq 1 $clients)
do
  # run nvflare client
  echo running site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/measure-image"
  pushd .
  cd $nvflare_workspace_dir
  # set env
  source ./set-env.sh
  # run
  ./remote-start.sh $infra > log.txt 2>&1 &
  popd

  sleep 2
done

# run server
echo running server...
nvflare_workspace_dir="$workspace_dir/server/measure-image"
pushd .
cd $nvflare_workspace_dir
# set env
source ./set-env.sh
# run
./remote-start.sh $job_name $clients > log.txt 2>&1 &
popd
