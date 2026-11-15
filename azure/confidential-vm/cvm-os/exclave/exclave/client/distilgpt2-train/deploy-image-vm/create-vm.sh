#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

SSH_PK=$(cat ~/.ssh/id_rsa.pub)
echo SSH public key...$SSH_PK

az vm create \
  --name $IMAGE_VM_NAME \
  --resource-group $AZURE_RESOURCE_GROUP \
  --size Standard_NC40ads_H100_v5 \
  --image Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest \
  --security-type Standard \
  --os-disk-name $IMAGE_VM_DISK_NAME \
  --admin-username "workspace" \
  --authentication-type ssh \
  --ssh-key-values "$SSH_PK"
