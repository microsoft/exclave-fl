# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

FROM docker.io/guojinnan/confidential-envoy-base:latest@sha256:6119d3360ae4afcf09f2626a26f875622bdc3814061b68faf5d49c301ceaf65c

RUN sudo apt-get update && sudo apt-get install -y gettext

RUN sudo apt install -y tpm2-tools && sudo apt install -y wget

RUN wget "https://packages.microsoft.com/repos/azurecore/pool/main/a/azguestattestation1/azguestattestation1_1.0.2_amd64.deb" && sudo dpkg -i azguestattestation1_1.0.2_amd64.deb

WORKDIR "/home/envoy"

COPY proxy-config-template.yaml proxy-config-template.yaml
COPY --chmod=755 bootstrap.sh bootstrap.sh
COPY AttestationClient AttestationClient

USER "envoy"
