#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# copy vm logs to the target path
run_name=$1
clients=$2
training_exclave=$3
target_path=$4

workspace_dir="${PWD}/../workspace-$run_name"
training_exclave_name="$training_exclave-train"
echo copying logs for workspace $workspace_dir, with $clients clients, and training exclave $training_exclave

for i in $(seq 1 $clients)
do
  # copy the log of the training exclave
  echo "--------------------------------------------------"
  echo copying the log of $training_exclave_name exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/$training_exclave_name/measure-image"
  cp $exclave_workspace_dir/log.txt $target_path/site-$i-$training_exclave.txt
  sleep 2

  # copy the log of the dp exclave
  echo "--------------------------------------------------"
  echo copying the log of svt-dp exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/svt-dp/measure-image"
  cp $exclave_workspace_dir/log.txt $target_path/site-$i-dp.txt
  sleep 2

  # copy the log of the nvflare client
  echo "--------------------------------------------------"
  echo copying the log of nvflare runtime for site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/nvflare/measure-image"
  cp $nvflare_workspace_dir/log.txt $target_path/site-$i.txt
  sleep 2
done

# copy the log of the aggregation exclave
echo "--------------------------------------------------"
echo copying the log of aggregation exclave for server...
exclave_workspace_dir="$workspace_dir/server/aggregation/measure-image"
cp $exclave_workspace_dir/log.txt $target_path/aggregation.txt
sleep 2

# copy the log of the model update exclave
echo "--------------------------------------------------"
echo copying the log of model update exclave for server...
exclave_workspace_dir="$workspace_dir/server/model-update/measure-image"
cp $exclave_workspace_dir/log.txt $target_path/model-update.txt
sleep 2

# copy the log of the nvflare server
echo "--------------------------------------------------"
echo copying the log of nvflare runtime for server...
nvflare_workspace_dir="$workspace_dir/server/nvflare/measure-image"
cp $nvflare_workspace_dir/log.txt $target_path/server.txt
sleep 2
