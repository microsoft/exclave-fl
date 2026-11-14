#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# source ./set-env.sh

# shared settings: azure/config.env (see azure/config.env.example)
_d=$PWD; while [ "$_d" != / ] && [ ! -f "$_d/load-config.sh" ]; do _d=$(dirname "$_d"); done
source "$_d/load-config.sh" || return 1; unset _d

# resource group
export AZURE_RESOURCE_GROUP="$RESOURCE_GROUP"
# name of vm that builds custom image
export IMAGE_VM_NAME="${DNS_PREFIX}vanilla-image"
# disk name of image vm
export IMAGE_VM_DISK_NAME="$IMAGE_VM_NAME-os-disk"
# storage account that stores .vhd file
export IMAGE_STORAGE_ACCOUNT_NAME="$STORAGE_ACCOUNT"
# storage container that stores .vhd file
export IMAGE_STORAGE_CONTAINER_NAME="vanilla-image"
# name of vm image gallery
export AZURE_IMAGE_GALLERY="$GALLERY"
# name of vm image definition
export AZURE_IMAGE_DEFINITION="vanilla"
# version of vm image
export AZURE_IMAGE_VERSION="$IMAGE_VERSION"
# name of vanilla vm that boots from custom image
export VANILLA_VM_NAME="${DNS_PREFIX}vanilla-server"
# name of vanilla vm os disk
export VANILLA_VM_DISK_NAME="$VANILLA_VM_NAME-os-disk"
# DNS tag of server
export VANILLA_VM_DNS_TAG="${DNS_PREFIX}vm-vanilla-fl"
