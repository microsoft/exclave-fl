#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# cleaning vms
run_name=$1
clients=$2
training_exclave=$3

workspace_dir="${PWD}/../workspace-$run_name"
training_exclave_name="$training_exclave-train"
echo running in workspace $workspace_dir, with $clients clients, and training exclave $training_exclave

# delete client
for i in $(seq 1 $clients)
do
  # delete training exclave
  echo deleting $training_exclave_name exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/$training_exclave_name/measure-image"
  pushd .
  cd $exclave_workspace_dir
  # set env
  source ./set-env.sh
  # delete
  ./cvm-delete.sh 2>&1 &
  popd

  sleep 2

  # delete dp exclave
  echo deleting svt-dp exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/svt-dp/measure-image"
  pushd .
  cd $exclave_workspace_dir
  # set env
  source ./set-env.sh
  # delete
  ./cvm-delete.sh 2>&1 &
  popd

  sleep 2

  # delete nvflare client
  echo deleting nvflare runtime for site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/nvflare/measure-image"
  pushd .
  cd $nvflare_workspace_dir
  # set env
  source ./set-env.sh
  # delete
  ./cvm-delete.sh 2>&1 &
  popd

  sleep 2
done

# delete server

# delete aggregation exclave
echo deleting aggregation exclave for server...
exclave_workspace_dir="$workspace_dir/server/aggregation/measure-image"
pushd .
cd $exclave_workspace_dir
# set env
source ./set-env.sh
# delete
./cvm-delete.sh 2>&1 &
popd

sleep 2

# delete model update exclave
echo deleting model update exclave for server...
exclave_workspace_dir="$workspace_dir/server/model-update/measure-image"
pushd .
cd $exclave_workspace_dir
# set env
source ./set-env.sh
# delete
./cvm-delete.sh 2>&1 &
popd

sleep 2

# delete nvflare server
echo deleting nvflare runtime for server...
nvflare_workspace_dir="$workspace_dir/server/nvflare/measure-image"
pushd .
cd $nvflare_workspace_dir
# set env
source ./set-env.sh
# delete
./cvm-delete.sh 2>&1 &
popd
