#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -e 

INFRA=$1

verityDeviceName=veritydevice1
verityDeviceNamePath="/dev/mapper/$verityDeviceName"

hashDevice=hash.img
dataDevice=data.img

if [ "$INFRA" == "--gpu" ]; then
    # in gpu vm size, sdb1 is the nvme storage, so the data disk is sdc1
    diskName="sdc1"
else
    diskName="sdb1"
fi

diskPath="/dev/$diskName"

mountPointDisk="/mnt/.disk"
mountPointData="/mnt/share"

# step 0. create mounting points
if [ ! -d "$mountPointDisk" ]; then
    mkdir -p "$mountPointDisk"
fi
 
if [ ! -d "$mountPointData" ]; then
    mkdir -p "$mountPointData"
fi

# step 1. Mount disk
mount $diskPath $mountPointDisk

# step 2. Open dm-verity device 
rootHash=$(cat "$mountPointDisk/root_hash")
echo "[!] Root hash... $rootHash"
echo "[!] Opening dm-verity protected images"
veritysetup open "$mountPointDisk/$dataDevice" $verityDeviceName "$mountPointDisk/$hashDevice" $rootHash

# step 3. mount data
mount -t ext4 "$verityDeviceNamePath" "$mountPointData"
ls $mountPointData
