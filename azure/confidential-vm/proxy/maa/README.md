# Create the MAA instance

## Introduction

The CVMs get their attestation tokens (JWT) from a custom MAA instance. These scripts create it and
set its policy.

You need `az` (logged in, with the `attestation` extension), Go 1.18+, `jq`, `curl` and `envsubst`.
The whole setup is in [azure/README.md, 3.1](../../../README.md#31-attestation-service-maa).

## Steps

1. Fill in `RESOURCE_GROUP` and `MAA_NAME` in `azure/config.env` (copy it from
   `azure/config.env.example`).
2. `source ./set_env.sh`
3. `./generate_policy.sh`
4. `./create_maa.sh`
5. `./sign_policy.sh`
6. `./set_policy.sh`
7. Put the endpoint that `set_policy.sh` prints (`MAA Endpoint ...`) into `MAA_ENDPOINT` in
   `azure/config.env`.

The signed policy file is `policy.jws`. You can also upload it in the Azure portal, as the
attestation policy for `AzureGuest`.

The scripts write `private_key.pem`, `cert.pem`, `cert.raw` and `policy.jws` here. They are
git-ignored; keep `private_key.pem` private.

`main.go`, `go.mod`, `go.sum`, `create_maa.sh`, `generate_policy.sh`, `sign_policy.sh`,
`set_policy.sh`, `arm-template.json`, `maa-parameters-template.json` and `policy.in.template` come
from [microsoft/confidential-ai](https://github.com/microsoft/confidential-ai) (MIT License).
