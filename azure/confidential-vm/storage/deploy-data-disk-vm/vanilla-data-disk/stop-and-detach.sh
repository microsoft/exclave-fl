#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# deallocate vm
az vm deallocate \
  --name $DISK_VM_NAME \
  --resource-group $AZURE_RESOURCE_GROUP

# delete vm (its data disks are detached automatically)
az vm delete \
  --name $DISK_VM_NAME \
  --resource-group $AZURE_RESOURCE_GROUP \
  --yes

