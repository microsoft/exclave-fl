#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -e

apt-get update
apt install -y tpm2-tools
apt install -y jq
apt install -y python3-pip python3-venv libtss2-dev pkg-config
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt

python3 attest.py &> attestation-benchmark.txt
