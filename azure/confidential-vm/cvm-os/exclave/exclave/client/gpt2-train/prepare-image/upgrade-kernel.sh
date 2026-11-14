#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# upgrade the kernel for building cgpu vm
INSTALL_PATH="/home/workspace"
cd $INSTALL_PATH/exclave-fl/third_party/conf-gpu/src
chmod +x *.sh
./step-0-prepare-kernel.sh
