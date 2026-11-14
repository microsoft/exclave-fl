# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# WikiText-103 data splitter
import argparse
import os

import numpy as np

# split into 4 pieces
SPLIT_NUM = 4

def data_split_args_parser():
    parser = argparse.ArgumentParser(description="Generate data split for dataset")
    parser.add_argument("--data-path", type=str, help="Path to data file")
    return parser


def main():
    parser = data_split_args_parser()
    args, unknown_args = parser.parse_known_args()
    data_path = args.data_path
    for mode in ["train", "valid", "test"]:
        input_file_path = os.path.join(data_path, "wiki." + mode + ".tokens")
        with open(input_file_path, 'r') as file:
            text = file.read() 
        split_1 = text[:len(text)//4]
        split_2 = text[len(text)//4:len(text)//2]
        split_3 = text[len(text)//2:3*len(text)//4]
        split_4 = text[3*len(text)//4:]
        data_splits = [split_1, split_2, split_3, split_4]
        for i in range(SPLIT_NUM):
            sub_dir = os.path.join(data_path, "site-" + str(i + 1))
            if not os.path.exists(sub_dir):
                os.mkdir(sub_dir)
            with open(os.path.join(sub_dir, "wiki." + mode + ".txt"), 'w') as file:
                file.write(data_splits[i])

if __name__ == "__main__":
    main()
