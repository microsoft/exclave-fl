# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os

import numpy as np
import torch
from torchvision import datasets, transforms

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