#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# running vms
run_name=$1
job_name=$2
clients=$3
training_exclave=$4
infra=$5

# Check if running with CGPU
if [ "$infra" == "--gpu" ]; then
  echo "Running Evaluation with H100 GPU VM"
else
  echo "Running Evaluation with CPU VM"
  infra=""
fi

workspace_dir="${PWD}/../workspace-$run_name"
training_exclave_name="$training_exclave-train"
echo running in workspace $workspace_dir, with $clients clients, and training exclave $training_exclave

# for each client
for i in $(seq 1 $clients)
do
  # run training exclave
  echo running $training_exclave_name exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/$training_exclave_name/measure-image"
  pushd .
  cd $exclave_workspace_dir
  # set env
  source ./set-env.sh
  # run
  ./remote-start.sh $infra > log.txt 2>&1 &
  popd

  sleep 2

  # run dp exclave
  echo running svt-dp exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/svt-dp/measure-image"
  pushd .
  cd $exclave_workspace_dir
  # set env
  source ./set-env.sh
  # run 
  ./remote-start.sh > log.txt 2>&1 &
  popd

  sleep 2

  # run nvflare client
  echo running nvflare runtime for site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/nvflare/measure-image"
  pushd .
  cd $nvflare_workspace_dir
  # set env
  source ./set-env.sh
  # run 
  ./remote-start.sh > log.txt 2>&1 &
  popd

  sleep 2
done

# run server

# run aggregation exclave
echo running aggregation exclave for server...
exclave_workspace_dir="$workspace_dir/server/aggregation/measure-image"
pushd .
cd $exclave_workspace_dir
# set env
source ./set-env.sh
# run
./remote-start.sh > log.txt 2>&1 &
popd

sleep 2

# run model update exclave
echo running model update exclave for server...
exclave_workspace_dir="$workspace_dir/server/model-update/measure-image"
pushd .
cd $exclave_workspace_dir
# set env
source ./set-env.sh
# run 
./remote-start.sh > log.txt 2>&1 &
popd

sleep 2

# run server
echo running server...
nvflare_workspace_dir="$workspace_dir/server/nvflare/measure-image"
pushd .
cd $nvflare_workspace_dir
# set env
source ./set-env.sh
# run
./remote-start.sh $job_name $clients > log.txt 2>&1 &
popd
