#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# create image gallery if it does not exist
# redirect stderr to stdout, stdout to /dev/null
SIG_SHOW_STDERR=$(az sig show --resource-group $AZURE_RESOURCE_GROUP --gallery-name $AZURE_IMAGE_GALLERY 2>&1 >/dev/null)

if [ -n "$SIG_SHOW_STDERR" ]; then
    # image gallery does not exist
    echo image gallery $AZURE_IMAGE_GALLERY does not exist. creating...
    az sig create --location westeurope --resource-group $AZURE_RESOURCE_GROUP --gallery-name $AZURE_IMAGE_GALLERY
else
    # image gallery exists
    echo image gallery $AZURE_IMAGE_GALLERY exists
fi

# create image definition if it does not exist
DEFI_SHOW_STDERR=$(az sig image-definition show --resource-group $AZURE_RESOURCE_GROUP --gallery-name $AZURE_IMAGE_GALLERY --gallery-image-definition $AZURE_IMAGE_DEFINITION 2>&1 >/dev/null) 

if [ -n "$DEFI_SHOW_STDERR" ]; then
    # image definition does not exist
    echo image definition $AZURE_IMAGE_DEFINITION does not exist. creating...
    az sig image-definition create --resource-group $AZURE_RESOURCE_GROUP --location westeurope --gallery-name $AZURE_IMAGE_GALLERY --gallery-image-definition $AZURE_IMAGE_DEFINITION --publisher exclavefl --offer ubuntu --sku $AZURE_IMAGE_DEFINITION --os-type Linux --os-state specialized --hyper-v-generation V2 --features SecurityType=ConfidentialVMSupported 
else
    # image definition exists
    echo image definition $AZURE_IMAGE_DEFINITION exists
fi

# create sig image version

# get storage account id
STORAGE_ACCOUNT_ID=$(az storage account show --name $IMAGE_STORAGE_ACCOUNT_NAME --resource-group $AZURE_RESOURCE_GROUP | jq -r .id)

echo storage account id $STORAGE_ACCOUNT_ID

# get blob url
VHD_FILE_NAME="protected-os.vhd"

VHD_BLOB_URI="https://${IMAGE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/${IMAGE_STORAGE_CONTAINER_NAME}/${VHD_FILE_NAME}"

echo image blob url $VHD_BLOB_URI

# check if image version exists
VERSION_SHOW_STDERR=$(az sig image-version show --resource-group $AZURE_RESOURCE_GROUP --gallery-name $AZURE_IMAGE_GALLERY --gallery-image-definition $AZURE_IMAGE_DEFINITION --gallery-image-version $AZURE_IMAGE_VERSION 2>&1 >/dev/null)

if [ -z "$VERSION_SHOW_STDERR" ]; then
   echo image version $AZURE_IMAGE_VERSION exists, deleting it
   az sig image-version delete --resource-group $AZURE_RESOURCE_GROUP --gallery-name $AZURE_IMAGE_GALLERY --gallery-image-definition $AZURE_IMAGE_DEFINITION --gallery-image-version $AZURE_IMAGE_VERSION
else
   echo image version $AZURE_IMAGE_VERSION does not exist...
fi

# create new image version
echo creating new image version...
# create the image version with the Compute REST API: osDiskImage.source takes the storage account id and the VHD blob uri
az rest --method put --url "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$AZURE_RESOURCE_GROUP/providers/Microsoft.Compute/galleries/$AZURE_IMAGE_GALLERY/images/$AZURE_IMAGE_DEFINITION/versions/$AZURE_IMAGE_VERSION?api-version=2023-07-03" \
  --body "{\"location\":\"westeurope\",\"properties\":{\"publishingProfile\":{\"targetRegions\":[{\"name\":\"westeurope\",\"regionalReplicaCount\":1}]},\"storageProfile\":{\"osDiskImage\":{\"source\":{\"storageAccountId\":\"$STORAGE_ACCOUNT_ID\",\"uri\":\"$VHD_BLOB_URI\"}}}}}"
az sig image-version wait --created --resource-group $AZURE_RESOURCE_GROUP --gallery-name $AZURE_IMAGE_GALLERY --gallery-image-definition $AZURE_IMAGE_DEFINITION --gallery-image-version $AZURE_IMAGE_VERSION

