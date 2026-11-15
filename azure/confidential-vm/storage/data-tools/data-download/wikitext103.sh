#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -e

DOWNLOAD_PATH=$1

WIKITEXT103_PATH="${DOWNLOAD_PATH}/wikitext103"

if [ ! -d "$WIKITEXT103_PATH" ]; then
	echo "Directory $WIKITEXT103_PATH does not exist. Creating..."
	mkdir -p $WIKITEXT103_PATH
else
	echo "Download Directory $WIKITEXT103_PATH exists"
fi

wget -c https://s3.amazonaws.com/datasets.huggingface.co/wikitext-103/wiki.train.tokens -P $WIKITEXT103_PATH
wget -c https://s3.amazonaws.com/datasets.huggingface.co/wikitext-103/wiki.valid.tokens -P $WIKITEXT103_PATH
wget -c https://s3.amazonaws.com/datasets.huggingface.co/wikitext-103/wiki.test.tokens -P $WIKITEXT103_PATH
