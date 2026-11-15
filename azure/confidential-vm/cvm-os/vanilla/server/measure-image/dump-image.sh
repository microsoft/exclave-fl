#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# deallocate image vm
az vm deallocate --name $IMAGE_VM_NAME --resource-group $AZURE_RESOURCE_GROUP

# get disk sas uri
export DISK_SAS_URI=$(az disk grant-access --duration-in-seconds 3600 --n $IMAGE_VM_DISK_NAME -g $AZURE_RESOURCE_GROUP --access-level Read | jq ".accessSas" | sed 's/"//g' )
echo SAS URI... $DISK_SAS_URI

# download vhd file
azcopy copy "$DISK_SAS_URI" reference-os.vhd

# create azure storage container if it does not exist
STORAGE_CONTAINER_STATUS=$(az storage container exists --account-name $IMAGE_STORAGE_ACCOUNT_NAME --name $IMAGE_STORAGE_CONTAINER_NAME --auth-mode login | grep exists | tail -c 5 | head -c 4)
if [[ $STORAGE_CONTAINER_STATUS != "true" ]]; then
    echo "Storage container $IMAGE_STORAGE_CONTAINER_NAME does not exist. Creating..."
    az storage container create --account-name $IMAGE_STORAGE_ACCOUNT_NAME --name $IMAGE_STORAGE_CONTAINER_NAME --auth-mode login
else
    echo "Storage container $IMAGE_STORAGE_CONTAINER_NAME exists"
fi

# upload os disk to storage container
az storage blob upload -f ${PWD}/reference-os.vhd -c $IMAGE_STORAGE_CONTAINER_NAME --account-name $IMAGE_STORAGE_ACCOUNT_NAME --overwrite --auth-mode key
