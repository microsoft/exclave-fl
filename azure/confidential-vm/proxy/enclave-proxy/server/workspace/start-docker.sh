#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# run the image loaded from the measured disk; --pull never stops Docker from fetching another copy
docker run -d --pull never --privileged --network host --mount type=bind,source=/sys/kernel/security,target=/sys/kernel/security --env MAA_ENDPOINT=$MAA_ENDPOINT --env ATTESTATION_POLICY=$ATTESTATION_POLICY "$IMAGESERVER/cvm-enclave-server-proxy:latest" /bin/bash -c ./bootstrap.sh
