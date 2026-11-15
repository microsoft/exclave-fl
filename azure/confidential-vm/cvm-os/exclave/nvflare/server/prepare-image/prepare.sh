#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# run this script with sudo privilege

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
apt install -y jq
apt install -y gettext-base

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

# install fl dependencies
INSTALL_PATH="/home/workspace"
python3 -m venv $INSTALL_PATH/env
source $INSTALL_PATH/env/bin/activate

# update setup tools
pip install --upgrade "setuptools<80"

pip install -r $INSTALL_PATH/exclave-fl/nvflare-ext/examples/evaluation/virtualenv/cvm-min-requirements.txt

# install torch
pip install -r $INSTALL_PATH/exclave-fl/nvflare-ext/examples/evaluation/virtualenv/cvm-torch-requirements.txt --index-url https://download.pytorch.org/whl/cu124

# cache the pinned Hugging Face models of the NLP jobs, so the jobs do not download them at run time
PYTHONPATH=$INSTALL_PATH/exclave-fl/nvflare-ext/examples/evaluation python3 - <<'EOF'
from pt.networks.nlp_models import BertModel, MobileBertModel, GPTModelCLM
BertModel("bert-base-uncased", num_labels=3)
MobileBertModel("google/mobilebert-uncased", num_labels=3)
GPTModelCLM("gpt2")
GPTModelCLM("distilgpt2")
EOF

# move start script
mv $INSTALL_PATH/exclave-fl/azure/confidential-vm/cvm-os/exclave/nvflare/server/cvm-start/cvm-start.sh $INSTALL_PATH/cvm-start.sh

# install nvflare
pushd .
cd $INSTALL_PATH/exclave-fl/nvflare-ext
pip install --ignore-installed PyYAML
pip install testresources
[ -f ../third_party/NVFlare/setup.py ] || { echo "missing NVFlare submodule: run 'git submodule update --init third_party/NVFlare' in the exclave-fl checkout"; exit 1; }
pip install ../third_party/NVFlare   # nvflare (pinned submodule)
pip install .           # confidential_fl (this directory)

# do provisioning
cd ./examples/evaluation
# fill in DNS_PREFIX (from config.env) in the VM host names
envsubst '${DNS_PREFIX}' < cvm_exclave_fl.yml > cvm_exclave_fl.rendered.yml
nvflare provision -p cvm_exclave_fl.rendered.yml

# create workspace
mkdir secure_workspace
mv ./workspace/cvm_exclave_project/prod_00/* ./secure_workspace
rm -r ./secure_workspace/site*
mv "./secure_workspace/${DNS_PREFIX}cvm-exclave-fl.westeurope.cloudapp.azure.com" ./secure_workspace/server
mv ./secure_workspace/admin* ./secure_workspace/admin

# configure the job files
mv ./job_upload ./job
# fill in the exclave DNS names in the job configs
for f in ./job/*/*/config/config_fed_*.json; do envsubst '${DNS_PREFIX}' < "$f" > "$f.tmp" && mv "$f.tmp" "$f"; done
popd

# pull sidecars
docker pull $IMAGESERVER/cvm-exclave-server-proxy:latest

# save image as tar file
pushd .
mkdir $INSTALL_PATH/sidecar_image
cd $INSTALL_PATH/sidecar_image
docker save -o cvm-exclave-server-proxy.tar $IMAGESERVER/cvm-exclave-server-proxy:latest
popd

# clean docker overlay
rm -rf /var/lib/docker
mkdir /var/lib/docker
chmod 710 /var/lib/docker

# stop docker
systemctl stop docker

# drop any registry login, so no credential ends up in the measured image
rm -rf /root/.docker

# change default ssh port
NEW_SSH_PORT=2222
sed -i "/^#Port 22/c\Port $NEW_SSH_PORT" /etc/ssh/sshd_config
