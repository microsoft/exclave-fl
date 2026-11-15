#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# quickly check vm status
run_name=$1
clients=$2
training_exclave=$3

workspace_dir="${PWD}/../workspace-$run_name"
training_exclave_name="$training_exclave-train"
echo running in workspace $workspace_dir, with $clients clients, and training exclave $training_exclave

for i in $(seq 1 $clients)
do
  # checking training exclave
  echo "--------------------------------------------------"
  echo checking $training_exclave_name exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/$training_exclave_name/measure-image"
  cat $exclave_workspace_dir/log.txt
  sleep 2

  # checking dp exclave
  echo "--------------------------------------------------"
  echo checking svt-dp exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/svt-dp/measure-image"
  cat $exclave_workspace_dir/log.txt
  sleep 2

  # checking nvflare client
  echo "--------------------------------------------------"
  echo checking nvflare runtime for site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/nvflare/measure-image"
  cat $nvflare_workspace_dir/log.txt
  sleep 2
done

# checking aggregation exclave
echo "--------------------------------------------------"
echo checking aggregation exclave for server...
exclave_workspace_dir="$workspace_dir/server/aggregation/measure-image"
cat $exclave_workspace_dir/log.txt
sleep 2

# checking model update exclave
echo "--------------------------------------------------"
echo checking model update exclave for server...
exclave_workspace_dir="$workspace_dir/server/model-update/measure-image"
cat $exclave_workspace_dir/log.txt
sleep 2

# checking nvflare server
echo "--------------------------------------------------"
echo checking nvflare runtime for server...
nvflare_workspace_dir="$workspace_dir/server/nvflare/measure-image"
cat $nvflare_workspace_dir/log.txt
sleep 2
