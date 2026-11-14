#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -e

DOWNLOAD_PATH=$1

NCBI_PATH="${DOWNLOAD_PATH}/ncbi"

if [ ! -d "$NCBI_PATH" ]; then
	echo "Directory $NCBI_PATH does not exist. Creating..."
	mkdir -p $NCBI_PATH
else
	echo "Download Directory $NCBI_PATH exists"
fi

wget -c 'https://docs.google.com/uc?export=download&id=1YWGBElsqj5ENsW0PtYwMlk_ShBt8MsLD' -O "${NCBI_PATH}/dev.csv"
wget -c 'https://docs.google.com/uc?export=download&id=12kXGQPW-do-F7T-TLGycl0DCw6eQIaZc' -O "${NCBI_PATH}/test.csv"
wget -c 'https://docs.google.com/uc?export=download&id=1fjsf0jFKWu_-bbx236oB6e7DqOqGmw3y' -O "${NCBI_PATH}/train.csv"

