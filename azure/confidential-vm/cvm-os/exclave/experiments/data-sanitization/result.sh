#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# copy vm logs to the target path
run_name=$1
clients=$2
target_path=$3

workspace_dir="${PWD}/../../workspace-$run_name"
echo copying logs for workspace $workspace_dir, for data sanitization exclave with $clients clients.

for i in $(seq 1 $clients)
do
  echo "--------------------------------------------------"
  echo copying the log of data sanitization exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/data-sanitization/measure-image"
  cp $exclave_workspace_dir/log.txt $target_path/site-$i-data-sanitization-exclave.txt

  sleep 2
done

