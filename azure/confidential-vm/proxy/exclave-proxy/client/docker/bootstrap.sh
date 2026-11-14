#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# Generate self-signed certificate
mkdir keys
mkdir certs
openssl req -x509 -newkey rsa:2048 -keyout keys/server-key.pem -out certs/server-cert.pem -days 100 -nodes -subj '/CN=envoy-server'

# Extract sha256 hash of the certificate and format it
export CERTIFICATE_HASH=$(openssl x509 -noout -sha256 -fingerprint -in certs/server-cert.pem | cut -f2 -d "=" |  sed -e "s/://g" | tr '[:upper:]' '[:lower:]')

# Generate an attestation token (the cvm attest lib base64-encodes the runtime data again)
RUNTIME_DATA=`jq --null-input '{"certificate_hash" : env.CERTIFICATE_HASH }' | base64 --wrap=0`
echo $RUNTIME_DATA

# Get host data (dm-verity measurement from pcr 11); the cvm library base64-encodes it
HOST_DATA=`sudo tpm2_pcrread sha256:11 | grep "11:" | sed 's/.*: 0x//'`
echo $HOST_DATA

RESPONSE=`sudo ./AttestationClient -a $MAA_ENDPOINT -r $RUNTIME_DATA -h $HOST_DATA -o token > attestation-token.txt`

echo Response from MAA...$RESPONSE
echo Decoded Response from MAA...
# decode jwt payload section
jq -R 'split(".") | .[1] | @base64d | fromjson' <<< `cat attestation-token.txt`

#obtain token validation certificate
MAA_OPENID_RESPONSE=`curl -X GET https://$MAA_ENDPOINT/.well-known/openid-configuration`
JWKS_URI=`echo $MAA_OPENID_RESPONSE | jq -r .jwks_uri`
JWKS_RESPONSE=`curl -X GET $JWKS_URI`
MAA_CERTIFICATE_CONTENT=`echo $JWKS_RESPONSE | jq -r .keys[0].x5c[0] | sed 's/-----.* CERTIFICATE-----//g'  | fold -w 63`
echo "-----BEGIN CERTIFICATE-----" > attestation-service-cert.pem
echo ${MAA_CERTIFICATE_CONTENT} >> attestation-service-cert.pem
echo "-----END CERTIFICATE-----" >> attestation-service-cert.pem
openssl x509 -pubkey -noout -in attestation-service-cert.pem > attestation-service-key.pem

if [[ -z "$ATTESTATION_POLICY" ]]; then
	  ATTESTATION_POLICY="ewp9"
fi

envsubst < proxy-config-template.yaml > proxy-config.yaml
envoy -c proxy-config.yaml
