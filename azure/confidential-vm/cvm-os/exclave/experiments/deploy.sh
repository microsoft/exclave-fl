#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# deploying vms
run_name=$1
clients=$2
training_exclave=$3
infra=$4

# Check if running with CGPU
if [ "$infra" == "--gpu" ]; then
  echo "Deploying Evaluation with H100 GPU VM"
else
  echo "Deploying Evaluation with CPU VM"
  infra=""
fi

workspace_dir="${PWD}/../workspace-$run_name"
training_exclave_name="$training_exclave-train"
echo running in workspace $workspace_dir, with $clients clients, and training exclave $training_exclave

# deploy client
for i in $(seq 1 $clients)
do
  # deploy training exclave
  echo deploying $training_exclave_name exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/$training_exclave_name/measure-image"
  pushd .
  cd $exclave_workspace_dir
  # set env
  source ./set-env.sh
  # deploy
  ./deploy-image.sh $infra 2>&1 &
  popd

  sleep 2

  # deploy dp exclave
  echo deploying svt-dp exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/svt-dp/measure-image"
  pushd .
  cd $exclave_workspace_dir
  # set env
  source ./set-env.sh
  # deploy 
  ./deploy-image.sh 2>&1 &
  popd

  sleep 2

  # deploy nvflare client
  echo deploying nvflare runtime for site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/nvflare/measure-image"
  pushd .
  cd $nvflare_workspace_dir
  # set env
  source ./set-env.sh
  # deploy 
  ./deploy-image.sh 2>&1 &
  popd

  sleep 2
done

# deploy server

# deploy aggregation exclave
echo deploying aggregation exclave for server...
exclave_workspace_dir="$workspace_dir/server/aggregation/measure-image"
pushd .
cd $exclave_workspace_dir
# set env
source ./set-env.sh
# deploy
./deploy-image.sh 2>&1 &
popd

sleep 2

# deploy model update exclave
echo deploying model update exclave for server...
exclave_workspace_dir="$workspace_dir/server/model-update/measure-image"
pushd .
cd $exclave_workspace_dir
# set env
source ./set-env.sh
# deploy 
./deploy-image.sh 2>&1 &
popd

sleep 2

# deploy nvflare server
echo deploying nvflare runtime for server...
nvflare_workspace_dir="$workspace_dir/server/nvflare/measure-image"
pushd .
cd $nvflare_workspace_dir
# set env
source ./set-env.sh
# deploy 
./deploy-image.sh 2>&1 &
popd
