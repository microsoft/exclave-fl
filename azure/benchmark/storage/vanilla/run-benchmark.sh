#!/bin/bash

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

set -e

disk_path="/dev/sdb"
partition_path="${disk_path}1"

apt-get update
apt install -y fio
apt install -y jq

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


MOUNT_POINT_DISK="/mnt/disk"
OUTPUT_PATH="/var/tmp/output"
mkdir -p "$MOUNT_POINT_DISK"
mkdir -p "$OUTPUT_PATH"

SIZES=("8G")
READFILENAME="$MOUNT_POINT_DISK/testfile"
export NUM_JOBS='1'
export BLOCK_SIZES='1m'

# Loop through each size
for SIZE in "${SIZES[@]}"
do

	# mount disk to target mounting point
	mount -t ext4 $partition_path $MOUNT_POINT_DISK
	# Determine the number of 1M blocks to write
	NUMBER=$(echo $SIZE | grep -oP '\d+')
	UNIT=$(echo $SIZE | grep -oP '[a-zA-Z]+')

	# Calculate the count based on unit
	if [ "$UNIT" == "G" ]; then
		COUNT=$(($NUMBER * 1024))
	elif [ "$UNIT" == "M" ]; then
		COUNT=$NUMBER
	fi

	echo "Creating $SIZE random data file..."
	
	dd if=/dev/urandom of=$READFILENAME bs=1M count=$COUNT

	# run fio
	for thread in $NUM_JOBS; do
		for bs in $BLOCK_SIZES; do
			export BLOCKSIZE=$bs
			export NUMJOBS=$thread
			export FILENAME="$MOUNT_POINT_DISK/testfile"
			echo "[!] BS: $BLOCKSIZE"
			echo "[!] Num jobs: $NUMJOBS"
			echo 3 > /proc/sys/vm/drop_caches
			fio sequential_read.fio --output-format="json" --output="${OUTPUT_PATH}/vanilla.seq_read.$SIZE.$bs.json"
		done
	done
	umount $MOUNT_POINT_DISK
done
