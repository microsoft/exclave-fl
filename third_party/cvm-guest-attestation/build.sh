#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# Build AttestationClient (upstream sample plus our patches) for the 5 proxy images. Needs docker.
set -e
cd "$(dirname "$0")"
./apply_patches.sh
docker run --rm -v "$PWD/upstream/cvm-attestation-sample-app:/src:ro" -v "$PWD:/out" \
  -e OWNER="$(id -u):$(id -g)" ubuntu:20.04 bash -c '
set -e
export DEBIAN_FRONTEND=noninteractive
# upstream README.md, "Build Instructions for Linux"
apt-get update
apt-get install -y build-essential libcurl4-openssl-dev libjsoncpp-dev libboost-all-dev cmake nlohmann-json3-dev wget
wget https://packages.microsoft.com/repos/azurecore/pool/main/a/azguestattestation1/azguestattestation1_1.0.2_amd64.deb
dpkg -i azguestattestation1_1.0.2_amd64.deb
cp -r /src /build && cd /build && cmake . && make
install -m 755 AttestationClient /out/AttestationClient && chown "$OWNER" /out/AttestationClient'
for d in enclave-proxy/client enclave-proxy/server exclave-proxy/client exclave-proxy/server exclave-proxy/exclave; do
  cp AttestationClient "../../azure/confidential-vm/proxy/$d/docker/AttestationClient"
done
rm AttestationClient
echo "AttestationClient built and copied into the 5 proxy image directories"
