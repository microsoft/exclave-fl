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
export IMAGE_VM_NAME="${DNS_PREFIX}enclave-image-server"
# disk name of image vm
export IMAGE_VM_DISK_NAME="$IMAGE_VM_NAME-os-disk"
# storage account that stores .vhd file
export IMAGE_STORAGE_ACCOUNT_NAME="$STORAGE_ACCOUNT"
# storage container that stores .vhd file
export IMAGE_STORAGE_CONTAINER_NAME="enclave-image-server"
# name of vm image gallery
export AZURE_IMAGE_GALLERY="$GALLERY"
# name of vm image definition
export AZURE_IMAGE_DEFINITION="enclave-server"
# version of vm image
export AZURE_IMAGE_VERSION="$IMAGE_VERSION"
# name of confidential vm that boots from custom image
export CONFIDENTIAL_VM_NAME="${DNS_PREFIX}enclave-server"
# name of confidential vm os disk
export CONFIDENTIAL_VM_DISK_NAME="$CONFIDENTIAL_VM_NAME-os-disk"
# DNS tag of server
export CONFIDENTIAL_VM_DNS_TAG="${DNS_PREFIX}cvm-enclave-fl"
# name of storage account that stores attestation policy
export ATTESTATION_POLICY_STORAGE_ACCOUNT_NAME="$STORAGE_ACCOUNT"
# name of storage container that stores attestation policy
export ATTESTATION_POLICY_STORAGE_CONTAINER_NAME="enclave-server"
