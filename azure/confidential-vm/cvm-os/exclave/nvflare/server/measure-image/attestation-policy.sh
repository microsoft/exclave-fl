#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# create storage container if it does not exist
STORAGE_CONTAINER_STATUS=$(az storage container exists --account-name $ATTESTATION_POLICY_STORAGE_ACCOUNT_NAME --name $ATTESTATION_POLICY_STORAGE_CONTAINER_NAME --auth-mode login | grep exists | tail -c 5 | head -c 4)
if [[ $STORAGE_CONTAINER_STATUS != "true" ]]; then
    echo "Storage container $ATTESTATION_POLICY_STORAGE_CONTAINER_NAME in storage account $ATTESTATION_POLICY_STORAGE_ACCOUNT_NAME does not exist. Creating..."
    az storage container create --account-name $ATTESTATION_POLICY_STORAGE_ACCOUNT_NAME --name $ATTESTATION_POLICY_STORAGE_CONTAINER_NAME --auth-mode login
else
    echo "Storage container $ATTESTATION_POLICY_STORAGE_CONTAINER_NAME exists"
fi

OS_MEASUREMENT=$(jq . protected-os_measurements.json)

# get pcr 11 value as init-time measurement, then convert to uppercase
MEASUREMENT=$(echo $OS_MEASUREMENT | jq -r '.CurrentPCRValues."SHA256"."11"' | tr '[:lower:]' '[:upper:]')

# do base64 encoding - don't include \n
export MEASUREMENT_BASE64=$(echo -n "$MEASUREMENT" | base64 -w0)

# output attestation policy
echo Runtime Claim: 
echo $MEASUREMENT_BASE64

ATTESTATION_TEMPLATE=$(jq . attestation_policy_template.json)
ATTESTATION_TEMPLATE=$(echo $ATTESTATION_TEMPLATE | jq '."x-ms-runtime.client-payload.hostdata" = env.MEASUREMENT_BASE64')
echo $ATTESTATION_TEMPLATE > attestation_policy.json

az storage blob upload -f ./attestation_policy.json -c $ATTESTATION_POLICY_STORAGE_CONTAINER_NAME --account-name $ATTESTATION_POLICY_STORAGE_ACCOUNT_NAME --overwrite --auth-mode key
