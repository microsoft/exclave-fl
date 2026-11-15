#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

FULL_DNS="$CONFIDENTIAL_VM_DNS_TAG.westeurope.cloudapp.azure.com"
EXCLAVE_DIR="${EXCLAVE_TYPE//-/_}"
ssh -p 2222 "workspace@$FULL_DNS" "sudo bash -c 'cd /home/workspace/$EXCLAVE_DIR && ./start.sh'"
