#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# shared settings: azure/config.env (see azure/config.env.example)
_d=$PWD; while [ "$_d" != / ] && [ ! -f "$_d/load-config.sh" ]; do _d=$(dirname "$_d"); done
source "$_d/load-config.sh" || return 1; unset _d

export AZURE_MAA_CUSTOM_RESOURCE_NAME="$MAA_NAME"
export AZURE_RESOURCE_GROUP="$RESOURCE_GROUP"
