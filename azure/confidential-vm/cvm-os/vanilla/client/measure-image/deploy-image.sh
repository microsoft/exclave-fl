#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

INFRA=$1

# Check if the first argument is --gpu
if [ "$INFRA" == "--gpu" ]; then
  echo "Deploying an H100 GPU VM"
  VM_SIZE="Standard_NC40ads_H100_v5"
else
  echo "Deploying a CPU VM"
  VM_SIZE="Standard_D32as_v5"
fi

# get gallery image id
AZURE_GALLERY_IMAGE_ID=$(az sig image-version show --gallery-image-definition $AZURE_IMAGE_DEFINITION --gallery-image-version $AZURE_IMAGE_VERSION --gallery-name $AZURE_IMAGE_GALLERY --resource-group $AZURE_RESOURCE_GROUP | jq -r .id)

# create vm
az vm create \
        --resource-group $AZURE_RESOURCE_GROUP \
        --name $VANILLA_VM_NAME \
	--location westeurope \
        --size $VM_SIZE \
        --image $AZURE_GALLERY_IMAGE_ID \
        --os-disk-name $VANILLA_VM_DISK_NAME \
        --security-type Standard \
        --public-ip-address-dns-name $VANILLA_VM_DNS_TAG \
        --specialized

# attach data disk
if [ -n "$DATA_DISK_NAME" ]; then
    echo attaching data disk...
    DATA_DISK_ID=$(az disk show -g $AZURE_RESOURCE_GROUP -n $DATA_DISK_NAME --query 'id' -o tsv)
    echo data disk id... $DATA_DISK_ID
    az vm disk attach -g $AZURE_RESOURCE_GROUP --vm-name $VANILLA_VM_NAME --name $DATA_DISK_ID
else
    echo "no data disk provided."
fi

# ssh inbound
az network nsg rule create --resource-group $AZURE_RESOURCE_GROUP --nsg-name ${VANILLA_VM_NAME}NSG -n Inbound2222Rule --access Allow --direction Inbound --source-port-ranges '*' --destination-port-ranges 2222 --priority 999
