#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# run this script with sudo privilege

set -e

# disable ubuntu 22.04 needrestart
sed -i 's/#$nrconf{restart} = '"'"'i'"'"';/$nrconf{restart} = '"'"'a'"'"';/g' /etc/needrestart/needrestart.conf

# install system dependencies
apt-get -y update 
apt install -y python3-pip
apt install -y python-is-python3
apt install -y python3-venv
apt install -y tpm2-tools
apt install -y libtss2-dev pkg-config
apt install -y jq

# install exclave dependencies
INSTALL_PATH="/home/workspace"
python3 -m venv $INSTALL_PATH/env
source $INSTALL_PATH/env/bin/activate

# install nvidia drivers
pushd .
cd $INSTALL_PATH/exclave-fl/third_party/conf-gpu/src
chmod +x *.sh
./step-1-install-gpu-driver.sh
# NVIDIA driver 580 sends the opaque data fields 33-36, which the pinned GPU verifier does not know
sed -i "/^ *21 *: 'OPAQUE_FIELD_ID_PROTECTED_PCIE_STATUS',\$/a\\        33  : 'OPAQUE_FIELD_ID_SYS_ENABLE_STATUS',\\n        34  : 'OPAQUE_FIELD_ID_OPAQUE_DATA_VERSION',\\n        35  : 'OPAQUE_FIELD_ID_CHIP_INFO',\\n        36  : 'OPAQUE_FIELD_ID_FEATURE_FLAG'," local_gpu_verifier/src/verifier/attestation/spdm_msrt_resp_msg.py
popd

# move exclave grpc server to workspace
mv $INSTALL_PATH/exclave-fl/azure/src/exclave/grpc_server/data_sanitization $INSTALL_PATH

# move exclave package to workspace
mv $INSTALL_PATH/exclave-fl/azure/src/exclave/exclave $INSTALL_PATH/data_sanitization

# move start script to workspace
mv $INSTALL_PATH/exclave-fl/azure/confidential-vm/cvm-os/exclave/exclave/client/data-sanitization/cvm-start/start.sh $INSTALL_PATH/data_sanitization

# update setup tools
pip install --upgrade setuptools

# install dependencies
pip install -r $INSTALL_PATH/data_sanitization/requirements-stable.txt
# install cu124 pytorch
pip install -r $INSTALL_PATH/data_sanitization/requirements-pre.txt --index-url https://download.pytorch.org/whl/cu124

# remove azure directory
cd $INSTALL_PATH
rm -r $INSTALL_PATH/exclave-fl/azure/confidential-vm/cvm-os
rm -r $INSTALL_PATH/exclave-fl/azure/src

# change default ssh port
NEW_SSH_PORT=2222
sed -i "/^#Port 22/c\Port $NEW_SSH_PORT" /etc/ssh/sshd_config
