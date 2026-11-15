#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -e

run_name=$1
n_client=$2
i=1
echo "Generating Workspace for Exclaves"
# generate new workspace for each run
workspace_dir="workspace-$run_name"
mkdir -p $workspace_dir/server/nvflare
mkdir -p $workspace_dir/client/nvflare

cp -r ./nvflare/server/* $workspace_dir/server/nvflare
cp -r ./nvflare/client/* $workspace_dir/client/nvflare

cp -r ./exclave/client/* $workspace_dir/client
cp -r ./exclave/server/* $workspace_dir/server

pushd .
cd $workspace_dir
while [ $i -le $n_client ]
do 
	cp -r client site-$i
	((i++))
done
# each client has its own workspace now; delete the template workspace
rm -r client
popd

echo "Generated workspace for run $run_name with $n_client client(s)"
