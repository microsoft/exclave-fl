#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# requires the az attestation extension
AZURE_MAA_ENDPOINT=`az attestation show --name $AZURE_MAA_CUSTOM_RESOURCE_NAME --resource-group $AZURE_RESOURCE_GROUP --query attestUri --output tsv | awk '{split($0,a,"//"); print a[2]}'`
echo MAA Endpoint $AZURE_MAA_ENDPOINT
MAA_POLICY_URI="https://$AZURE_MAA_ENDPOINT/policies/AzureGuest?api-version=2022-08-01"
BEARER_TOKEN=`az account get-access-token --resource https://attest.azure.net --query accessToken --output tsv`
POLICY=`cat policy.jws`

curl -X PUT -H "Authorization:Bearer $BEARER_TOKEN" -H "Content-Type: text/plain" -d "$POLICY" "$MAA_POLICY_URI"
