#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# deploying vms
run_name=$1
clients=$2
infra=$3

# Check if running with CGPU
if [ "$infra" == "--gpu" ]; then
  echo "Deploying Evaluation with H100 GPU VM"
else
  echo "Deploying Evaluation with CPU VM"
  infra=""
fi


workspace_dir="${PWD}/../workspace-$run_name"
echo running in workspace $workspace_dir, with $clients clients

# deploy client
for i in $(seq 1 $clients)
do
  echo deploying site-$i...
  nvflare_workspace_dir="$workspace_dir/site-$i/measure-image"
  pushd .
  cd $nvflare_workspace_dir
  # set env
  source ./set-env.sh
  # deploy 
  ./deploy-image.sh $infra 2>&1 &
  popd

  sleep 2
done

# deploy server
echo deploying server...
nvflare_workspace_dir="$workspace_dir/server/measure-image"
pushd .
cd $nvflare_workspace_dir
# set env
source ./set-env.sh
# deploy 
./deploy-image.sh 2>&1 &
popd
