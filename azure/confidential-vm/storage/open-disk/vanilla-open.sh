#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -e 

INFRA=$1

if [ "$INFRA" == "--gpu" ]; then
    # in gpu vm size, sdb1 is the nvme storage, so the data disk is sdc1
    diskName="sdc1"
else
    diskName="sdb1"
fi

diskPath="/dev/$diskName"

mountPointData="/mnt/share"

# create mount point
if [ ! -d "$mountPointData" ]; then
    mkdir -p "$mountPointData"
fi

# mount
mount -t ext4 $diskPath $mountPointData
ls $mountPointData
