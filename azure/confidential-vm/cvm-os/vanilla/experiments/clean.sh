#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# cleaning vms
run_name=$1
clients=$2

workspace_dir="${PWD}/../workspace-$run_name"
echo running in workspace $workspace_dir, with $clients clients

# delete client
for i in $(seq 1 $clients)
do
  echo deleting site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/measure-image"
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
echo deleting server...
nvflare_workspace_dir="$workspace_dir/server/measure-image"
pushd .
cd $nvflare_workspace_dir
# set env
source ./set-env.sh
# delete
./cvm-delete.sh 2>&1 &
popd
