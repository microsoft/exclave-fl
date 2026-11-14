#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

INFRA=$1
CLIENT_ID=$(echo "$CLIENT_NAME" | grep -o '[0-9]\+')
FULL_DNS="$CONFIDENTIAL_VM_DNS_TAG.westeurope.cloudapp.azure.com"
# download attestation policy
az storage blob download -f "attestation_policy.json" --container-name "enclave-server" --account-name $ATTESTATION_POLICY_STORAGE_ACCOUNT_NAME -n attestation_policy.json --auth-mode key
# upload attestation policy
scp -P 2222 attestation_policy.json "workspace@$FULL_DNS:~/"
ssh -p 2222 "workspace@$FULL_DNS" "sudo bash -c 'cd /home/workspace && ./cvm-start.sh \"$CLIENT_ID\" \"$INFRA\"'"
