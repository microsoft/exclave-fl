#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

run_name=$1
n_client=$2
i=1
echo "Generating Workspace for Enclaves"
# generate new workspace for each run
workspace_dir="workspace-$run_name"
mkdir $workspace_dir
cp -r server $workspace_dir
cp -r client $workspace_dir

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
