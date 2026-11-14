#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -e

DOWNLOAD_PATH=$1

CIFAR10_PATH="${DOWNLOAD_PATH}/cifar10"

if [ ! -d "$CIFAR10_PATH" ]; then
	echo "Directory $CIFAR10_PATH does not exist. Creating..."
	mkdir -p $CIFAR10_PATH
else
	echo "Download Directory $CIFAR10_PATH exists"
fi

wget -c https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz -P $CIFAR10_PATH

pushd $CIFAR10_PATH
tar -xvf cifar-10-python.tar.gz
popd
