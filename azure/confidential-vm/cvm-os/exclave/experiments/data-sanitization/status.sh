#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# quickly check vm status
run_name=$1
clients=$2

workspace_dir="${PWD}/../../workspace-$run_name"
echo in workspace $workspace_dir, checking data sanitization exclave for $clients clients.

for i in $(seq 1 $clients)
do
  # checking data sanitization exclave
  echo "--------------------------------------------------"
  echo checking data-sanitization exclave for site-$i...
  exclave_workspace_dir="$workspace_dir/site-$i/data-sanitization/measure-image"
  cat $exclave_workspace_dir/log.txt
  sleep 2
done