# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
#
# This file is modified from code under the following notice:
#
# Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# NCBI data splitter
import argparse
import os

import numpy as np
import pandas as pd

SPLIT_NUM = 4

def data_split_args_parser():
    parser = argparse.ArgumentParser(description="Generate data split for dataset")
    parser.add_argument("--data-path", type=str, help="Path to data file")
    return parser


def split_df_by_num(df, num=1):
    df_len = df.shape[0]
    df_1_len = num
    idx = list(range(df_len))
    df_1 = df.iloc[idx[:df_1_len]]
    df_2 = df.iloc[idx[df_1_len:]]
    df_1.reset_index(drop=True, inplace=True)
    df_2.reset_index(drop=True, inplace=True)
    return df_1, df_2


def main():
    parser = data_split_args_parser()
    args, unknown_args = parser.parse_known_args()
    num_clients = SPLIT_NUM
    data_path = args.data_path
    for mode in ["train", "dev"]:
        saved_name = "val" if mode == "dev" else mode
        df = pd.read_csv(os.path.join(data_path, mode + ".csv"))
        client_size = int(df.shape[0] / num_clients)
        os.makedirs(f"{data_path}/{num_clients}_split", exist_ok=True)
        for i in range(num_clients):
            # create subdirectory
            sub_dir = os.path.join(data_path, "site-" + str(i + 1))
            if not os.path.exists(sub_dir):
                os.mkdir(sub_dir)
            if i != num_clients - 1:
                client_df, df = split_df_by_num(df, client_size)
            else:
                client_df = df
            print(df.shape, client_df.shape)
            # split into train, test, val
            client_df.to_csv(f"{sub_dir}/{saved_name}.csv")

if __name__ == "__main__":
    main()
