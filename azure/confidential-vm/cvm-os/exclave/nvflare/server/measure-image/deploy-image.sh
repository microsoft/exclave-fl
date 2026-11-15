#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# get gallery image id
AZURE_GALLERY_IMAGE_ID=$(az sig image-version show --gallery-image-definition $AZURE_IMAGE_DEFINITION --gallery-image-version $AZURE_IMAGE_VERSION --gallery-name $AZURE_IMAGE_GALLERY --resource-group $AZURE_RESOURCE_GROUP | jq -r .id)

# create cvm
az vm create \
        --resource-group $AZURE_RESOURCE_GROUP \
        --name $CONFIDENTIAL_VM_NAME \
	--location westeurope \
        --size Standard_EC8as_v5 \
        --enable-vtpm true \
        --enable-secure-boot false \
        --image $AZURE_GALLERY_IMAGE_ID \
	--os-disk-name $CONFIDENTIAL_VM_DISK_NAME \
	--os-disk-security-encryption-type VMGuestStateOnly \
        --security-type ConfidentialVM \
        --public-ip-address-dns-name $CONFIDENTIAL_VM_DNS_TAG \
        --specialized

# create network security rule
az network nsg rule create --resource-group $AZURE_RESOURCE_GROUP --nsg-name ${CONFIDENTIAL_VM_NAME}NSG -n Inbound8102Rule --access Allow --direction Inbound --source-port-ranges '*' --destination-port-ranges 8102 --priority 1010

az network nsg rule create --resource-group $AZURE_RESOURCE_GROUP --nsg-name ${CONFIDENTIAL_VM_NAME}NSG -n Inbound8103Rule --access Allow --direction Inbound --source-port-ranges '*' --destination-port-ranges 8103 --priority 1011

az network nsg rule create --resource-group $AZURE_RESOURCE_GROUP --nsg-name ${CONFIDENTIAL_VM_NAME}NSG -n Inbound2222Rule --access Allow --direction Inbound --source-port-ranges '*' --destination-port-ranges 2222 --priority 999
