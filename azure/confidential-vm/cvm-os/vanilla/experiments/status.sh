#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# quickly check vm status
run_name=$1
clients=$2

workspace_dir="${PWD}/../workspace-$run_name"
echo running in workspace $workspace_dir, with $clients clients

# check client status
for i in $(seq 1 $clients)
do
  echo "--------------------------------------------------"
  echo checking site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/measure-image"
  cat $nvflare_workspace_dir/log.txt
  sleep 2
done

# check server status
echo "--------------------------------------------------"
echo checking server...
nvflare_workspace_dir="$workspace_dir/server/measure-image"
cat $nvflare_workspace_dir/log.txt