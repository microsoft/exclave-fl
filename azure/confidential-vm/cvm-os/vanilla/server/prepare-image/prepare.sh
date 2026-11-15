#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# run this script with sudo privilege

set -e

# settings: azure/config.env (see azure/config.env.example)
source /home/workspace/exclave-fl/azure/load-config.sh || exit 1

# disable ubuntu 22.04 needrestart
sed -i 's/#$nrconf{restart} = '"'"'i'"'"';/$nrconf{restart} = '"'"'a'"'"';/g' /etc/needrestart/needrestart.conf

# install system dependencies
apt-get -y update 
apt install -y python3-pip
apt install -y python-is-python3
apt install -y python3-venv
apt install -y jq
apt install -y gettext-base

# create python venv
INSTALL_PATH="/home/workspace"
python3 -m venv $INSTALL_PATH/env
source $INSTALL_PATH/env/bin/activate

# install nvidia drivers
sudo apt install -y gcc g++ make
sudo apt install -y nvidia-driver-550-server-open linux-modules-nvidia-550-server-open-azure

# update setup tools
pip install --upgrade "setuptools<80"

# install fl dependencies
pip install -r $INSTALL_PATH/exclave-fl/nvflare-ext/examples/evaluation/virtualenv/cvm-min-requirements.txt
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
mv $INSTALL_PATH/exclave-fl/azure/confidential-vm/cvm-os/vanilla/server/vm-start/server-start.sh $INSTALL_PATH/server-start.sh 
mv $INSTALL_PATH/exclave-fl/azure/confidential-vm/cvm-os/vanilla/client/vm-start/client-start.sh $INSTALL_PATH/client-start.sh

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
envsubst '${DNS_PREFIX}' < vm_vanilla_fl.yml > vm_vanilla_fl.rendered.yml
nvflare provision -p vm_vanilla_fl.rendered.yml
# move workspace
mkdir secure_workspace
mv ./workspace/vm_vanilla_project/prod_00/* ./secure_workspace
mv "./secure_workspace/${DNS_PREFIX}vm-vanilla-fl.westeurope.cloudapp.azure.com" ./secure_workspace/server

# configure the job files
mv ./job_upload ./job
# fill in the exclave DNS names in the job configs
for f in ./job/*/*/config/config_fed_*.json; do envsubst '${DNS_PREFIX}' < "$f" > "$f.tmp" && mv "$f.tmp" "$f"; done
popd

# change default ssh port
NEW_SSH_PORT=2222
sed -i "/^#Port 22/c\Port $NEW_SSH_PORT" /etc/ssh/sshd_config
