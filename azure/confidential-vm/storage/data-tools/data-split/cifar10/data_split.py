# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

# Cifar10 Data Splitter
import argparse
import os

import numpy as np
import torch
from torchvision import datasets, transforms

def data_split_args_parser():
    parser = argparse.ArgumentParser(description="Generate data split for dataset")
    parser.add_argument("--data-path", type=str, help="Path to data file")
    parser.add_argument("--num-clients", type=int, help="Total number of clients")
    return parser

def unison_shuffled_copies(a, b):
    assert len(a) == len(b)
    p = np.random.permutation(len(a))
    return a[p], b[p]

# Split data before deployment
def split_data(path: str, num_client: int):
    train_cifar_dataobj = datasets.CIFAR10(root=path, train=True)
    test_cifar_dataobj = datasets.CIFAR10(root=path, train=False)
    train_data = train_cifar_dataobj.data
    test_data = test_cifar_dataobj.data
    train_target = np.array(train_cifar_dataobj.targets)
    test_target = np.array(test_cifar_dataobj.targets)
    # repeat the dataset num_clients times, then shuffle it
    train_data_shuffle, train_target_shuffle = unison_shuffled_copies(np.tile(train_data, (num_client,1,1,1)), np.tile(train_target, num_client))
    test_data_shuffle, test_target_shuffle = unison_shuffled_copies(np.tile(test_data, (num_client,1,1,1)), np.tile(test_target, num_clients))
    train_data_all = np.array_split(train_data_shuffle, num_client)
    train_target_all = np.array_split(train_target_shuffle, num_client)
    test_data_all = np.array_split(test_data_shuffle, num_client)
    test_target_all = np.array_split(test_target_shuffle, num_client)
    i = 0
    while i < len(train_data_all):
        # create subdirectory
        sub_dir = os.path.join(path, "site-" + str(i + 1))
        if not os.path.exists(sub_dir):
            os.mkdir(sub_dir)
        train_data_file_name = "train_data" + ".npy"
        train_target_file_name = "train_target" + ".npy"
        test_data_file_name = "test_data" + ".npy"
        test_target_file_name = "test_target" + ".npy"
        np.save(os.path.join(sub_dir, train_data_file_name), train_data_all[i])
        np.save(os.path.join(sub_dir, train_target_file_name), train_target_all[i])
        np.save(os.path.join(sub_dir, test_data_file_name), test_data_all[i])
        np.save(os.path.join(sub_dir, test_target_file_name), test_target_all[i])
        i += 1

# Dataset of one client's split
class SplittedData(torch.utils.data.Dataset):
    def __init__(self, root, train, transform):
        self.root = root
        self.train = train
        self.transform = transform
        self.data, self.target = self.__build_subset__()

    def __build_subset__(self):
        if self.train is True:
            data = np.load(os.path.join(self.root, "train_data.npy"))
            target = np.load(os.path.join(self.root, "train_target.npy"))
        else:
            data = np.load(os.path.join(self.root, "test_data.npy"))
            target = np.load(os.path.join(self.root, "test_target.npy"))
        return data, target

    def __getitem__(self, index):
        img, target = self.data[index], self.target[index]
        if self.transform is not None:
            img = self.transform(img)
        return img, target

    def __len__(self):
        return len(self.data)

def load_data(root_path: str):
    dataset = SplittedData(root_path, True, None)
    train_loader = torch.utils.data.DataLoader(
        dataset, batch_size=64, shuffle=True, num_workers=0
    )
    print(len(train_loader))

if __name__ == "__main__":
    parser = data_split_args_parser()
    args = parser.parse_args()
    num_clients = args.num_clients
    data_path = args.data_path
    split_data(data_path, num_clients)


