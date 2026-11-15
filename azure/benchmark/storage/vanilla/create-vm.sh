#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

SSH_PK=$(cat ~/.ssh/id_rsa.pub)
echo SSH public key...$SSH_PK

# create vm
az vm create \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $BENCHMARK_VM_NAME \
  --location westeurope \
  --size Standard_D32as_v5 \
  --image Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest \
  --security-type Standard \
  --os-disk-name $BENCHMARK_VM_DISK_NAME \
  --admin-username "workspace" \
  --authentication-type ssh \
  --ssh-key-values "$SSH_PK"


DISK_NAME="vanilla-benchmark"
DISK_SHOW_STDERR=$(az disk show --resource-group $AZURE_RESOURCE_GROUP -n $DISK_NAME 2>&1 >/dev/null)
if [ -n "$DISK_SHOW_STDERR" ]; then
    # data disk does not exist
    echo [!] vanilla benchmark disk does not exist...
    echo [!] creating vanilla benchmark disk...
    # create data disk with P30 performance tier
    az disk create -n $DISK_NAME -g $AZURE_RESOURCE_GROUP -l westeurope --sku Premium_LRS --size-gb 16 --tier P30
    # attach the created disk to the benchmark vm
    az vm disk attach --vm-name $BENCHMARK_VM_NAME -g $AZURE_RESOURCE_GROUP --name $DISK_NAME
else
    # data disk exists
    echo [!] vanilla benchmark disk exists
    echo [!] attaching vanilla benchmark disk...
    # update existing data disk to P30
    az disk update -n $DISK_NAME -g $AZURE_RESOURCE_GROUP --set tier=P30
    # attach data disk to vm
    az vm disk attach --vm-name $BENCHMARK_VM_NAME -g $AZURE_RESOURCE_GROUP --name $DISK_NAME
fi
