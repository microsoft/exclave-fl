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
  --size Standard_DC4as_v5 \
  --enable-vtpm true \
  --enable-secure-boot false \
  --image Canonical:0001-com-ubuntu-confidential-vm-jammy:22_04-lts-cvm:latest \
  --security-type ConfidentialVM \
  --os-disk-name $BENCHMARK_VM_DISK_NAME \
  --os-disk-security-encryption-type VMGuestStateOnly \
  --admin-username "workspace" \
  --authentication-type ssh \
  --ssh-key-values "$SSH_PK"

