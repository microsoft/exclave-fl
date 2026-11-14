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

import os
import logging
import numpy as np
import pandas as pd
import torch
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from seqeval.metrics import classification_report

from pt.networks.nlp_models import BertModel, MobileBertModel
from pt.utils.data_sequence import DataSequence

from exclave.service.training_exclave.training_exclave import TrainingExclave
from exclave.utils.constants import DATA_PATH

os.environ["TOKENIZERS_PARALLELISM"] = "false"

class NCBITrainExclave(TrainingExclave):
    def __init__(
        self,
        model_name: str,
        epochs: int = 1,
        lr: float = 1e-5,
        batch_size: int = 32,
        num_labels: int = 3,
        ignore_token: int = -100
    ):
        """NLP Training Exclave on NCBI Dataset
        """
        super().__init__()

        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.num_labels = num_labels
        self.ignore_token = ignore_token
        self.model_name = model_name

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
            if self.model_name == "google/mobilebert-uncased":
                self.model = MobileBertModel(model_name=self.model_name, num_labels=self.num_labels)
            elif self.model_name == "bert-base-uncased":
                self.model = BertModel(model_name=self.model_name, num_labels=self.num_labels)
            else:
                raise ValueError(f"Model {self.model_name} is not supported by NLP Exclave.")
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=self.lr)
        tokenizer = self.model.tokenizer
        # load data
        if self.train_loader is None or self.valid_loader is None:
            logging.info("Loading data")
            # load data
            df_train, df_valid = self.load_data()
            # get labels from data
            self.get_labels(df_train)
            # create dataset
            train_dataset = DataSequence(df_train, self.labels_to_ids, tokenizer=tokenizer, ignore_token=self.ignore_token)
            valid_dataset = DataSequence(df_valid, self.labels_to_ids, tokenizer=tokenizer, ignore_token=self.ignore_token)
            self.train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)
            self.valid_loader = DataLoader(valid_dataset, batch_size=self.batch_size, shuffle=False)
            # a sequence has 150 tokens
            logging.info(f"Num Sequences = {len(train_dataset)}; Num tokens = {len(train_dataset)*150}")

    # load data
    def load_data(self):
        df_train = pd.read_csv(os.path.join(DATA_PATH, "train.csv"))
        df_valid = pd.read_csv(os.path.join(DATA_PATH, "val.csv"))
        return df_train, df_valid

    # get labels from data
    def get_labels(self, df_train):
        labels = []
        for x in df_train["labels"].values:
            labels.extend(x.split(" "))
        unique_labels = set(labels)
        self.labels_to_ids = {k: v for v, k in enumerate(sorted(unique_labels))}
        self.ids_to_labels = {v: k for v, k in enumerate(sorted(unique_labels))}

    # nlp training logic
    def train(self, train_loader, global_weights):
        logging.info("Start local training")
        for epoch in range(self.epochs):
            self.model.train()
            epoch_len = len(train_loader)
            self.epoch_global = self.epoch_of_start_time + epoch
            avg_loss = 0.0
            # inputs, labels
            for i, batch_data in enumerate(train_loader):
                mask = batch_data[0]["attention_mask"].squeeze(1).to(self.device)
                input_id = batch_data[0]["input_ids"].squeeze(1).to(self.device)
                train_label = batch_data[1].to(self.device)
                # optimize
                loss, logits = self.model(input_id, mask, train_label)
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
                current_step = epoch_len * self.epoch_global + i
                avg_loss += loss.item()
            logging.info("loss of this epoch is {}".format(avg_loss / len(train_loader)))
        model_diff = self.get_model_diff(global_weights)
        return model_diff
    
    # nlp validation logic
    def valid(self, valid_loader):
        self.model.eval()
        with torch.no_grad():
            total_acc_val, total_loss_val, val_total = 0, 0, 0
            val_y_pred, val_y_true = [], []
            for val_data, val_label in valid_loader:
                val_label = val_label.to(self.device)
                val_total += val_label.shape[0]
                mask = val_data["attention_mask"].squeeze(1).to(self.device)
                input_id = val_data["input_ids"].squeeze(1).to(self.device)
                # Inference
                loss, logits = self.model(input_id, mask, val_label)
                # Add items for metric computation
                for i in range(logits.shape[0]):
                    # remove pad tokens
                    logits_clean = logits[i][val_label[i] != self.ignore_token]
                    label_clean = val_label[i][val_label[i] != self.ignore_token]
                    # calculate acc and store prediction and true labels
                    predictions = logits_clean.argmax(dim=1)
                    acc = (predictions == label_clean).float().mean()
                    total_acc_val += acc.item()
                    val_y_pred.append([self.ids_to_labels[x.item()] for x in predictions])
                    val_y_true.append([self.ids_to_labels[x.item()] for x in label_clean])
            # compute metric
            metric_dict = classification_report(y_true=val_y_true, y_pred=val_y_pred, output_dict=True, zero_division=0)
        return metric_dict["macro avg"]["f1-score"]
