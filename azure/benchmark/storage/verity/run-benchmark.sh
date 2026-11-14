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


HASH_DEVICE="hash.img"
DATA_DEVICE="data.img"
MOUNT_POINT_DISK="/mnt/.disk"
MOUNT_POINT_DATA="/mnt/data"
OUTPUT_PATH="/var/tmp/output"
mkdir -p "$MOUNT_POINT_DISK"
mkdir -p "$MOUNT_POINT_DATA"
mkdir -p "$OUTPUT_PATH"

VERITY_DEVICE_NAME="veritydevice1"
VERITY_DEVICE_PATH="/dev/mapper/$VERITY_DEVICE_NAME"


SIZES=("8G")
FILE_PATH="/data"
mkdir -p $FILE_PATH
READFILENAME="$FILE_PATH/testfile"
export NUM_JOBS='1'
export BLOCK_SIZES='1m'


# Loop through each size
for SIZE in "${SIZES[@]}"
do

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

	# create dm-verity
	MOUNT_POINT_TMP=$(mktemp -d)
	# data device size is 1.5 times the file size
	truncate --size "$(( $COUNT * 15 / 10 ))M" "$DATA_DEVICE"
	echo [!] formatting $DATA_DEVICE as ext4
	mkfs.ext4 $DATA_DEVICE
	echo [!] mounting $DATA_DEVICE to $MOUNT_POINT_TMP
	mount -t ext4 "$DATA_DEVICE" "$MOUNT_POINT_TMP" -o loop
	mv "$READFILENAME" "$MOUNT_POINT_TMP"
	ls "$MOUNT_POINT_TMP"
	umount "$MOUNT_POINT_TMP"

	echo [!] formatting dm-verity
	veritysetup -v --debug format $DATA_DEVICE $HASH_DEVICE | grep 'Root hash:' | tail -c 65 | head -c 64 | sudo tee root_hash
	mount -t ext4 "$partition_path" "$MOUNT_POINT_TMP"
	mv $DATA_DEVICE $HASH_DEVICE root_hash $MOUNT_POINT_TMP
	umount $MOUNT_POINT_TMP
	rm -r $MOUNT_POINT_TMP

	# mount dm-verity
	mount $partition_path $MOUNT_POINT_DISK

	# open dm-verity device
	ROOT_HASH=$(cat "$MOUNT_POINT_DISK/root_hash")
	echo "[!] Root hash... $ROOT_HASH"
	echo "[!] Opening dm-verity protected images"
	veritysetup open "$MOUNT_POINT_DISK/$DATA_DEVICE" $VERITY_DEVICE_NAME "$MOUNT_POINT_DISK/$HASH_DEVICE" $ROOT_HASH

	# mount data
	mount -t ext4 "$VERITY_DEVICE_PATH" "$MOUNT_POINT_DATA"

	# run fio
	for thread in $NUM_JOBS; do
		for bs in $BLOCK_SIZES; do
			export BLOCKSIZE=$bs
			export NUMJOBS=$thread
			export FILENAME="$MOUNT_POINT_DATA/testfile"
			echo "[!] Running Sequential Read"
			echo "[!] BS: $BLOCKSIZE"
			echo "[!] Num jobs: $NUMJOBS"
			echo 3 > /proc/sys/vm/drop_caches
			fio sequential_read.fio --output-format="json" --output="${OUTPUT_PATH}/verity.seq_read.$SIZE.$bs.json"
		done
	done
	# close dm-verity
	umount $MOUNT_POINT_DATA
	veritysetup close $VERITY_DEVICE_NAME
	umount $MOUNT_POINT_DISK
done
