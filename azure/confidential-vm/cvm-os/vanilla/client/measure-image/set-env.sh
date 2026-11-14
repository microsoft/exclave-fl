#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# source ./set-env.sh

# shared settings: azure/config.env (see azure/config.env.example)
_d=$PWD; while [ "$_d" != / ] && [ ! -f "$_d/load-config.sh" ]; do _d=$(dirname "$_d"); done
source "$_d/load-config.sh" || return 1; unset _d

# resource group
export AZURE_RESOURCE_GROUP="$RESOURCE_GROUP"
# client name
export CLIENT_NAME="$(basename $(dirname $PWD))"
# name of vm image gallery
export AZURE_IMAGE_GALLERY="$GALLERY"
# name of vm image definition
export AZURE_IMAGE_DEFINITION="vanilla"
# version of vm image
export AZURE_IMAGE_VERSION="$IMAGE_VERSION"
# name of vanilla vm that boots from custom image
export VANILLA_VM_NAME="${DNS_PREFIX}vanilla-${CLIENT_NAME}"
# name of vanilla vm os disk
export VANILLA_VM_DISK_NAME="$VANILLA_VM_NAME-os-disk"
# dns tag
export VANILLA_VM_DNS_TAG="${DNS_PREFIX}vanilla-fl-${CLIENT_NAME}"
# name of data disk to be attached to vanilla vm
export DATA_DISK_NAME="vanilla-data-${CLIENT_NAME}"
