#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

IMAGESERVER=$1

docker build -t $IMAGESERVER/cvm-exclave-proxy -f Dockerfile .
