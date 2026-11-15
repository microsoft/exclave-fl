#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

while getopts ":k:" options; do
    case $options in
        k)rsaKeyFile=$OPTARG;;    
    esac
done

if [ -f "$rsaKeyFile" ]; then
    go run main.go -p /tmp/maa-policy.in -k $rsaKeyFile
else
    echo "Passing private_key.pem key file as default"
    go run main.go -p /tmp/maa-policy.in -k private_key.pem
fi
