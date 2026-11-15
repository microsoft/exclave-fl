#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

SSH_PK=$(cat ~/.ssh/id_rsa.pub)
echo SSH public key...$SSH_PK

# create vm
az vm create \
  --name $DISK_VM_NAME \
  --resource-group $AZURE_RESOURCE_GROUP \
  --location westeurope \
  --size Standard_DC4as_v5 \
  --enable-vtpm true \
  --enable-secure-boot false \
  --image Canonical:0001-com-ubuntu-confidential-vm-jammy:22_04-lts-cvm:latest \
  --security-type ConfidentialVM \
  --os-disk-security-encryption-type VMGuestStateOnly \
  --admin-username "workspace" \
  --authentication-type ssh \
  --ssh-key-values "$SSH_PK"

# create data disk
i=1
while [ $i -le $NUM_CLIENTS ]
do
    DISK_NAME="vanilla-data-site-$i"
    DISK_SHOW_STDERR=$(az disk show --resource-group $AZURE_RESOURCE_GROUP -n $DISK_NAME 2>&1 >/dev/null)
    if [ -n "$DISK_SHOW_STDERR" ]; then
        # data disk does not exist
	echo [!] data disk for client site-"$i" does not exist...
	echo [!] creating data disk: $DISK_NAME...
	# create data disk with P30 performance tier
	az disk create -n $DISK_NAME -g $AZURE_RESOURCE_GROUP -l westeurope --sku Premium_LRS --size-gb 4 --tier P30
	# attach the created disk to the disk vm
	az vm disk attach --vm-name $DISK_VM_NAME -g $AZURE_RESOURCE_GROUP --name $DISK_NAME
    else
	# data disk exists
	echo [!] data disk for client site-"$i" exists
	echo [!] updating and attaching data disk: $DISK_NAME
	# update existing data disk to P30
	az disk update -n $DISK_NAME -g $AZURE_RESOURCE_GROUP --set tier=P30
	# attach data disk to vm
	az vm disk attach --vm-name $DISK_VM_NAME -g $AZURE_RESOURCE_GROUP --name $DISK_NAME
    fi
    ((i++))
done
