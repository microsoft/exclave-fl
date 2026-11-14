#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# use az disk integrity tool to measure a customized image with dm-verity

# deallocate image vm
az vm deallocate --name $IMAGE_VM_NAME --resource-group $AZURE_RESOURCE_GROUP

# get disk sas uri
export DISK_SAS_URI=$(az disk grant-access --duration-in-seconds 3600 --n $IMAGE_VM_DISK_NAME -g $AZURE_RESOURCE_GROUP --access-level Read | jq ".accessSas" | sed 's/"//g' )
echo SAS URI... $DISK_SAS_URI

# download vhd file
azcopy copy "$DISK_SAS_URI" reference-os.vhd

# prepare disk
VHDSIZE=$(ls -l ./reference-os.vhd | awk '{print $5}')
LOOP_DEVICE=$(sudo losetup -P -o 0 --sizelimit $(($VHDSIZE - 512)) --sector-size 512 -f "./reference-os.vhd" --show)
sudo sgdisk -e $LOOP_DEVICE
sudo sgdisk -s $LOOP_DEVICE
sudo losetup -d $LOOP_DEVICE

# specialize the disk (the tool adds the cvmadmin account; ssh and scp log in as workspace)
sudo -E az cvm osdisk specialize --source ./reference-os.vhd --hostname cvmfl --username cvmadmin --ssh-key-file ~/.ssh/id_rsa.pub --output-file ./specialized-os.vhd

# integrity protect the disk
sudo -E az cvm osdisk integrity-protect \
    --source ./specialized-os.vhd \
        --output-file ./protected-os.vhd

# create azure storage container if it does not exist
STORAGE_CONTAINER_STATUS=$(az storage container exists --account-name $IMAGE_STORAGE_ACCOUNT_NAME --name $IMAGE_STORAGE_CONTAINER_NAME --auth-mode login | grep exists | tail -c 5 | head -c 4)
if [[ $STORAGE_CONTAINER_STATUS != "true" ]]; then
    echo "Storage container $IMAGE_STORAGE_CONTAINER_NAME does not exist. Creating..."
    az storage container create --account-name $IMAGE_STORAGE_ACCOUNT_NAME --name $IMAGE_STORAGE_CONTAINER_NAME --auth-mode login
else
    echo "Storage container $IMAGE_STORAGE_CONTAINER_NAME exists"
fi

az storage blob upload -f ./protected-os.vhd -c $IMAGE_STORAGE_CONTAINER_NAME --account-name $IMAGE_STORAGE_ACCOUNT_NAME --overwrite --auth-mode key
