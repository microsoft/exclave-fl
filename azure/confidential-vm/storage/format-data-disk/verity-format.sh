#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# run this script with sudo privilege

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <number_of_clients> <dataset name>"
    exit 1
fi

num_clients=$1
dataset=$2

data_tools_path="/home/workspace/exclave-fl/azure/confidential-vm/storage/data-tools"

# Step 0. Install dependencies
apt-get update
apt install -y python3-pip
pip install -r $data_tools_path/requirements.txt

# Step 1. Download and Split dataset

# step 1.1 download dataset
echo downloading dataset $dataset
$data_tools_path/data-download/$dataset.sh "/tmp"
 
# step 1.2 split dataset
echo creating split for $dataset dataset
python3 $data_tools_path/data-split/$dataset/data_split.py --num-clients=$num_clients --data-path="/tmp/$dataset"

# Step 2. Create disk partition and format dm-verity

hash_device=hash.img
data_device=data.img

data_path="/tmp/$dataset"

# ASCII of "b"
start_ascii=$(printf "%d" "'b")

# ASCII of last drive
end_ascii=$((start_ascii + num_clients - 1))

# convert to letter
end_drive=$(printf "\x$(printf %x $end_ascii)")

# step 2.1 create partition and format as ext4
# step 2.2 create dm-verity protected disk
client_id=1
for drive in $(eval echo {b..$end_drive}); do
    disk_path="/dev/sd${drive}"
    partition_path="${disk_path}1"
    # create a partition on a newly created disk; reformat an existing one
    echo partition operation on $disk_path
    if [ -e "$partition_path" ]; then
        echo "partition $partition_path already exists..."
	# wipe disk content and reformat as ext4
	mkfs.ext4 -F $partition_path
    else
        echo "partition $partition_path does not exist..."
        echo "creating partition for $disk_path"
        parted $disk_path --script mklabel gpt mkpart ext4part ext4 0% 100%
	sleep 2
        mkfs.ext4 $partition_path
	partprobe $partition_path
    fi

    # formatting dm-verity
    mount_point=$(mktemp -d)
    truncate --size 2G "$data_device"
    echo [!] formatting $data_device as ext4
    mkfs.ext4 $data_device
    echo [!] mounting $data_device to $mount_point
    mount -t ext4 "$data_device" "$mount_point" -o loop
    cp -r $data_path/site-${client_id}/* "$mount_point"
    ls $mount_point
    umount "$mount_point"

    echo [!] formatting dm-verity
    veritysetup -v --debug format $data_device $hash_device | grep 'Root hash:' | tail -c 65 | head -c 64 | sudo tee root_hash
    mount -t ext4 "$partition_path" "$mount_point"
    mv $data_device $hash_device root_hash $mount_point
    ls $mount_point
    umount $mount_point
    rm -r $mount_point
    ((client_id++))
done    
