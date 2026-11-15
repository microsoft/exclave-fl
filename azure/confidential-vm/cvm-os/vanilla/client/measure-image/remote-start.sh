#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

INFRA=$1
CLIENT_ID=$(echo "$CLIENT_NAME" | grep -o '[0-9]\+')
FULL_DNS="$VANILLA_VM_DNS_TAG.westeurope.cloudapp.azure.com"
ssh -p 2222 "workspace@$FULL_DNS" "cd /home/workspace && sudo bash ./client-start.sh $CLIENT_ID $INFRA"
