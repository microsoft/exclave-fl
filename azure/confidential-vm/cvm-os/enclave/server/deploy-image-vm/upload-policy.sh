#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

PUBLIC_IP=$1

# download attestation policy
az storage blob download -f "attestation_policy.json" --container-name "enclave-client" --account-name $ATTESTATION_POLICY_STORAGE_ACCOUNT_NAME -n attestation_policy.json --auth-mode key
# upload attestation policy
scp attestation_policy.json "workspace@$PUBLIC_IP:~/"

