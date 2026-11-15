#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

IMAGESERVER=$1

docker build -t $IMAGESERVER/cvm-enclave-server-proxy -f Dockerfile .
