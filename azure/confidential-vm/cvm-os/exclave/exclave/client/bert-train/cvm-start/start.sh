#!/usr/bin/env bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# run this script with sudo privilege

# settings: azure/config.env, which the image keeps (MAA_ENDPOINT, IMAGESERVER)
source /home/workspace/exclave-fl/azure/load-config.sh || exit 1

INFRA=$1

# Check if the first argument is --gpu
if [ "$INFRA" == "--gpu" ]; then
  echo "Running FL training with GPU support"
  nvidia-smi conf-compute -f
  nvidia-smi conf-compute -e
else
  echo "Running FL training under CPU setting "
fi

# if using H100
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
docker load -i cvm-exclave-proxy.tar
popd

# load env var for proxy
: "${MAA_ENDPOINT:?missing from azure/config.env}"
# base64 of an empty JSON object
export ATTESTATION_POLICY="ewp9"

# config and run proxy
pushd .
echo [!] start proxy...
cd /home/workspace/exclave-fl/azure/confidential-vm/proxy/exclave-proxy/exclave/workspace
./iptable.sh
./start-docker.sh &
popd

# config disk and open verity device
pushd .
cd /home/workspace/exclave-fl/azure/confidential-vm/storage/open-disk
# check if using H100
if [ "$INFRA" == "--gpu" ]; then
  echo "gpu setting - data disk is in /dev/sdc1"
  ./verity-open.sh --gpu
else
  echo "cpu setting - data disk is in /dev/sdb1"
  ./verity-open.sh
fi
popd

# start training exclave 
# activate venv
source /home/workspace/env/bin/activate
# add current folder to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}"
echo "PYTHONPATH is ${PYTHONPATH}"
python3 training_exclave.py
