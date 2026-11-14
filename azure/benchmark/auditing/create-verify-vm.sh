#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

SSH_PK=$(cat ~/.ssh/id_rsa.pub)
echo SSH public key...$SSH_PK

# create vm
az vm create \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $VERIFY_VM_NAME \
  --location westeurope \
  --size Standard_D4as_v5 \
  --image Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest \
  --security-type Standard \
  --os-disk-name $VERIFY_VM_DISK_NAME \
  --admin-username "workspace" \
  --authentication-type ssh \
  --ssh-key-values "$SSH_PK"

