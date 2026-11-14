#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# delete vm
az vm delete -g $AZURE_RESOURCE_GROUP -n $VANILLA_VM_NAME --force-deletion yes --yes

# delete os disk
az disk delete -g $AZURE_RESOURCE_GROUP -n $VANILLA_VM_DISK_NAME --yes
