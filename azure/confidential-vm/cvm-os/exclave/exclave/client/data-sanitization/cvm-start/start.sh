#!/usr/bin/env bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# run this script with sudo privilege

INFRA=$1

# activate venv
source /home/workspace/env/bin/activate

# Check if the first argument is --gpu
if [ "$INFRA" == "--gpu" ]; then
  echo "Running data sanitization with GPU support"
else
  echo "Running data sanitization under CPU setting "
fi

# if using H100
if [ "$INFRA" == "--gpu" ]; then
  # gpu attestation
  pushd .
  cd /home/workspace/exclave-fl/third_party/conf-gpu/src
  ./step-2-attestation.sh
  # fetch measurements
  mv ./local_gpu_verifier/verifier.log ./verifier.log
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
  # check driver status
  nvidia-smi conf-compute -f
  nvidia-smi conf-compute -e
  popd

  # umount /dev/sdb1 (the default nvme storage of the gpu vm size)
  umount /dev/sdb1
fi

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

# start data sanitization exclave
# add current folder to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}"
echo "PYTHONPATH is ${PYTHONPATH}"
python3 data_sanitization_exclave.py
