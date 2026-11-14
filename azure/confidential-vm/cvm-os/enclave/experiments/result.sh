#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# copy vm logs to the target path
run_name=$1
clients=$2
target_path=$3

workspace_dir="${PWD}/../workspace-$run_name"
echo copying logs for workspace $workspace_dir, with $clients clients

for i in $(seq 1 $clients)
do
  # copy the log of the nvflare client
  echo "--------------------------------------------------"
  echo copying the log of nvflare runtime for site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/measure-image"
  cp $nvflare_workspace_dir/log.txt $target_path/site-$i.txt
  sleep 2
done

# copy the log of the nvflare server
echo "--------------------------------------------------"
echo copying the log of nvflare runtime for server...
nvflare_workspace_dir="$workspace_dir/server/measure-image"
cp $nvflare_workspace_dir/log.txt $target_path/server.txt
sleep 2
