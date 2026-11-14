#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# cleaning vms
run_name=$1
clients=$2

workspace_dir="${PWD}/../../workspace-$run_name"
echo cleaning in workspace $workspace_dir, for data sanitization exclave with $clients clients.

# delete client
for i in $(seq 1 $clients)
do
  # delete data sanitization exclave
  echo deleting data sanitization exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/data-sanitization/measure-image"
  pushd .
  cd $exclave_workspace_dir
  # set env
  source ./set-env.sh
  # delete
  ./cvm-delete.sh 2>&1 &
  popd

  sleep 2
done