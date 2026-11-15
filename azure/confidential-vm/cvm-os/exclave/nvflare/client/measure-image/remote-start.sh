#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

CLIENT_ID=$(echo "$CLIENT_NAME" | grep -o '[0-9]\+')
FULL_DNS="$CONFIDENTIAL_VM_DNS_TAG.westeurope.cloudapp.azure.com"
# run job
ssh -p 2222 "workspace@$FULL_DNS" "sudo bash -c 'cd /home/workspace && ./cvm-start.sh \"$CLIENT_ID\"'"
