#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# settings: azure/config.env, which the image keeps (MAA_ENDPOINT, IMAGESERVER)
source /home/workspace/exclave-fl/azure/load-config.sh || exit 1

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <client_id> <--cpu or --gpu>"
  exit 1
fi

CLIENT_ID=$1
INFRA=$2

# Check if the second argument is --gpu
if [ "$INFRA" == "--gpu" ]; then
  echo "Running FL training with GPU support"
  nvidia-smi conf-compute -f
  nvidia-smi conf-compute -e
else
  echo "Running FL training under CPU setting "
fi

if [ "$INFRA" == "--gpu" ]; then
  # measure gpu
  pushd .
  cd /home/workspace/exclave-fl/third_party/conf-gpu/src/local_gpu_verifier
  python3 -m verifier.cc_admin
  # fetch measurements
  awk '
  /Runtime measurements are :/ {
    count=64
    next
  }
  count > 0 {
    gsub(/^[ \t]+/, ""); # Remove leading spaces and tabs from each line
    sub(/[ \t]+$/, "");  # Remove trailing spaces and tabs from each line
    line = (line ? line : "") $0
    count--
  }
  END {
    printf "%s", line
  }
  ' "verifier.log" > gpu_measurement
  cat ./gpu_measurement | sha256sum | awk '{print $1}' | head -c 64 > gpu_sha256
  # extend gpu measurement into pcr16
  export GPU_MEASUREMENT=$(cat ./gpu_sha256)
  tpm2_pcrextend "16:sha256=$GPU_MEASUREMENT"
  popd

  # umount /dev/sdb1 (the default nvme storage of the gpu vm size)
  umount /dev/sdb1
fi

# load docker image
pushd .
echo [!] loading docker images...
cd /home/workspace/sidecar_image
docker load -i cvm-enclave-client-proxy.tar
popd

# load env var for proxy
: "${MAA_ENDPOINT:?missing from azure/config.env}"

# attestation policy, copied to the vm with scp
export ATTESTATION_POLICY=$(cat /home/workspace/attestation_policy.json | base64 -w0)
echo [!] attestation policy... $ATTESTATION_POLICY

# config and run proxy
pushd .
echo [!] start proxy...
cd /home/workspace/exclave-fl/azure/confidential-vm/proxy/enclave-proxy/client/workspace
./iptable.sh
./start-docker.sh &
popd

# config disk and open verity device
pushd .
cd /home/workspace/exclave-fl/azure/confidential-vm/storage/open-disk
# Check if the second argument is --gpu
if [ "$INFRA" == "--gpu" ]; then
  echo "gpu setting - data disk is in /dev/sdc1"
  ./verity-open.sh --gpu
else
  echo "cpu setting - data disk is in /dev/sdb1"
  ./verity-open.sh
fi
popd

# extend data commitment into pcr 23
export DATA_COMMITMENT=$(cat /mnt/.disk/root_hash)
tpm2_pcrextend "23:sha256=$DATA_COMMITMENT" 

# start running nvflare client
cd /home/workspace/exclave-fl/nvflare-ext/examples/evaluation
source /home/workspace/env/bin/activate
echo [!] running nvflare client...
# add current folder to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}"
echo "PYTHONPATH is ${PYTHONPATH}"
workspace="${PWD}/secure_workspace"
site_name="site-${CLIENT_ID}"
${workspace}/${site_name}/startup/nvflare_start.sh &
