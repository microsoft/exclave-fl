#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

JOB_NAME=$1
MIN_CLIENTS=$2

FULL_DNS="$CONFIDENTIAL_VM_DNS_TAG.westeurope.cloudapp.azure.com"
ssh -p 2222 "workspace@$FULL_DNS" "sudo bash -c 'cd /home/workspace && ./cvm-start.sh \"$JOB_NAME\" \"$MIN_CLIENTS\"'"
