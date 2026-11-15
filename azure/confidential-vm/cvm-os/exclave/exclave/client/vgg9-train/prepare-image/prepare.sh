#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# run this script with sudo privilege

set -e

# settings: azure/config.env (see azure/config.env.example)
source /home/workspace/exclave-fl/azure/load-config.sh || exit 1
# the registry and the MAA endpoint come from config.env only; stop now if either is missing
[ $# -eq 0 ] || { echo "error: prepare.sh takes no arguments; set IMAGESERVER in azure/config.env" >&2; exit 1; }
: "${IMAGESERVER:?set IMAGESERVER in azure/config.env}"
: "${MAA_ENDPOINT:?set MAA_ENDPOINT in azure/config.env}"

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

# install docker
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update

# install docker engine
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# the measured CVM root is an overlay, so Docker needs the vfs storage driver
echo '{"storage-driver": "vfs"}' > /etc/docker/daemon.json
systemctl restart docker

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
# cgpu attestation
./step-2-attestation.sh
# check driver status
nvidia-smi conf-compute -f
nvidia-smi conf-compute -e
popd

# move exclave grpc server to workspace
mv $INSTALL_PATH/exclave-fl/azure/src/exclave/grpc_server/vgg9_train $INSTALL_PATH

# move exclave package to workspace
mv $INSTALL_PATH/exclave-fl/azure/src/exclave/exclave $INSTALL_PATH/vgg9_train

# move start script to workspace
mv $INSTALL_PATH/exclave-fl/azure/confidential-vm/cvm-os/exclave/exclave/client/vgg9-train/cvm-start/start.sh $INSTALL_PATH/vgg9_train

# update setup tools
pip install --upgrade setuptools

# install dependencies
pip install -r $INSTALL_PATH/vgg9_train/requirements-stable.txt
# install cu124 pytorch
pip install -r $INSTALL_PATH/vgg9_train/requirements-pre.txt --index-url https://download.pytorch.org/whl/cu124

# pull sidecars
docker pull $IMAGESERVER/cvm-exclave-proxy:latest

# save image as tar file
pushd .
mkdir $INSTALL_PATH/sidecar_image
cd $INSTALL_PATH/sidecar_image
docker save -o cvm-exclave-proxy.tar $IMAGESERVER/cvm-exclave-proxy:latest
popd

# clean docker overlay
rm -rf /var/lib/docker
mkdir /var/lib/docker
chmod 710 /var/lib/docker

# stop docker
systemctl stop docker

# drop any registry login, so no credential ends up in the measured image
rm -rf /root/.docker

# remove azure directory
cd $INSTALL_PATH
rm -r $INSTALL_PATH/exclave-fl/azure/confidential-vm/cvm-os
rm -r $INSTALL_PATH/exclave-fl/azure/src

# change default ssh port
NEW_SSH_PORT=2222
sed -i "/^#Port 22/c\Port $NEW_SSH_PORT" /etc/ssh/sshd_config
