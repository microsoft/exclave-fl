# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
#
# This file is modified from code under the following notice:
#
# Copyright (c) 2021-2022, NVIDIA CORPORATION.
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

import numpy as np
import logging
import torch
import torch.optim as optim
from torchvision import datasets, transforms

from pt.networks.cv_models import LeNet, VGG9
from pt.utils.cifar10_splitted_data import SplittedData

from exclave.service.training_exclave.training_exclave import TrainingExclave
from exclave.utils.constants import DATA_PATH

class Cifar10TrainExclave(TrainingExclave):
    def __init__(
        self,
        model_name : str= "vgg9",
        epochs: int = 1,
        lr: float = 1e-2,
        batch_size: int = 64,
        momentum: float = 0.9
    ):
        """CIFAR-10 Training Exclave.
        """
        super().__init__()

        self.model_name = model_name
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.momentum = momentum

        self.device = None
        self.model = None
        self.optimizer = None
        self.criterion = None
        self.transform_train = None
        self.transform_valid = None
        self.train_dataset = None
        self.valid_dataset = None
        self.train_loader = None
        self.valid_loader = None

        self.epoch_of_start_time = 0
        self.epoch_global = 0

    def initialize(self):
        # training setup
        if self.model is None:
            if self.model_name == "lenet":
                self.model = LeNet()
            elif self.model_name == "vgg9":
                self.model = VGG9() 
            else:
                raise ValueError(f"Model {self.model_name} is not supported by Cifar10 Exclave")
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.optimizer = optim.SGD(self.model.parameters(), lr=self.lr, momentum=self.momentum)
        self.criterion = torch.nn.CrossEntropyLoss()
        # dataset setup
        self.transform_train = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.ToPILImage(),
                transforms.Pad(4, padding_mode="reflect"),
                transforms.RandomCrop(32),
                transforms.RandomHorizontalFlip(),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[x / 255.0 for x in [125.3, 123.0, 113.9]],
                    std=[x / 255.0 for x in [63.0, 62.1, 66.7]],
                ),
            ]
        )
        self.transform_valid = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[x / 255.0 for x in [125.3, 123.0, 113.9]],
                    std=[x / 255.0 for x in [63.0, 62.1, 66.7]],
                ),
            ]
        )
        # only load data once
        if self.train_dataset is None or self.train_loader is None:

            self.train_dataset = SplittedData(
                root=DATA_PATH,
                train=True,
                transform=self.transform_train,
            )
            self.train_loader = torch.utils.data.DataLoader(
                self.train_dataset, batch_size=self.batch_size, shuffle=True
            )

        if self.valid_dataset is None or self.valid_loader is None:
            self.valid_dataset = SplittedData(
                root=DATA_PATH,
                train=False,
                transform=self.transform_valid,
            )
            self.valid_loader = torch.utils.data.DataLoader(
                self.valid_dataset, batch_size=self.batch_size, shuffle=False
            )
    
    # cifar10 training logic
    def train(self, train_loader, global_weights):
        logging.info("Start local training")
        for epoch in range(self.epochs):
            logging.info("Training Epoch {}".format(epoch))
            self.model.train()
            epoch_len = len(train_loader)
            self.epoch_global = self.epoch_of_start_time + epoch
            avg_loss = 0.0
            for i, (inputs, labels) in enumerate(train_loader):
                inputs, labels = inputs.to(self.device), labels.to(self.device)
                # zero the parameter gradients
                self.optimizer.zero_grad()
                # forward + backward + optimize
                outputs = self.model(inputs)
                loss = self.criterion(outputs, labels)
                loss.backward()
                self.optimizer.step()
                current_step = epoch_len * self.epoch_global + i
                avg_loss += loss.item()
            logging.info("loss of this epoch is {}".format(avg_loss / len(train_loader)))
        model_diff = self.get_model_diff(global_weights)
        return model_diff
    
    # cifar10 validation logic
    def valid(self, valid_loader):
        self.model.eval()
        with torch.no_grad():
            correct, total = 0, 0
            for _i, (inputs, labels) in enumerate(valid_loader):
                inputs, labels = inputs.to(self.device), labels.to(self.device)
                outputs = self.model(inputs)
                _, pred_label = torch.max(outputs.data, 1)

                total += inputs.data.size()[0]
                correct += (pred_label == labels.data).sum().item()
            metric = correct / float(total)
        return metric
