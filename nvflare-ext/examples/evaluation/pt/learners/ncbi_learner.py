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
import numpy as np
import pandas as pd
import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader
from seqeval.metrics import classification_report

from nvflare.apis.dxo import DXO, DataKind, MetaKey, from_shareable
from nvflare.apis.fl_constant import FLContextKey, ReturnCode
from nvflare.apis.fl_context import FLContext
from nvflare.apis.shareable import Shareable, make_reply
from nvflare.apis.signal import Signal
from nvflare.app_common.abstract.learner_spec import Learner
from nvflare.app_common.app_constant import AppConstants, ValidateType

from pt.networks.nlp_models import BertModel, GPTModelTC, MobileBertModel
from pt.utils.data_sequence import DataSequence

os.environ["TOKENIZERS_PARALLELISM"] = "false"

NCBI_ROOT = "/mnt/share"

class NCBILearner(Learner):
    def __init__(
        self,
        learning_rate: float = 1e-5,
        batch_size: int = 32,
        model_name: str = "google/mobilebert-uncased",
        num_labels: int = 3,
        ignore_token: int = -100,
        aggregation_epochs: int = 1,
    ):
        """Supervised NLP Learner.
        """
        super().__init__()
        self.aggregation_epochs = aggregation_epochs
        self.model_name = model_name
        self.num_labels = num_labels
        self.ignore_token = ignore_token
        self.lr = learning_rate
        self.batch_size = batch_size
        # client ID
        self.client_id = None
        # Epoch counter
        self.epoch_of_start_time = 0
        self.epoch_global = 0
        # Training-related
        self.train_loader = None
        self.valid_loader = None
        self.optimizer = None
        self.device = None
        self.model = None
        self.labels_to_ids = None
        self.ids_to_labels = None

    def load_data(self):
        df_train = pd.read_csv(os.path.join(NCBI_ROOT, "train.csv"))
        df_valid = pd.read_csv(os.path.join(NCBI_ROOT, "val.csv"))
        return df_train, df_valid

    def get_labels(self, df_train, fl_ctx):
        labels = []
        for x in df_train["labels"].values:
            labels.extend(x.split(" "))
        unique_labels = set(labels)
        # check label length
        if len(unique_labels) != self.num_labels:
            self.system_panic(
                f"num_labels {self.num_labels} need to align with dataset, actual data {len(unique_labels)}!", fl_ctx
            )
            return make_reply(ReturnCode.EXECUTION_EXCEPTION)
        self.labels_to_ids = {k: v for v, k in enumerate(sorted(unique_labels))}
        self.ids_to_labels = {v: k for v, k in enumerate(sorted(unique_labels))}

    def initialize(self, parts: dict, fl_ctx: FLContext):
    
        if self.model is None:
            if self.model_name == "google/mobilebert-uncased":
                self.model = MobileBertModel(model_name=self.model_name, num_labels=self.num_labels)
            elif self.model_name == "bert-base-uncased":
                self.model = BertModel(model_name=self.model_name, num_labels=self.num_labels)
            elif self.model_name == "gpt2":
                self.model = GPTModelTC(model_name=self.model_name, num_labels=self.num_labels)
            else:
                self.system_panic(f"Model {self.model} not supported!", fl_ctx)
                return make_reply(ReturnCode.EXECUTION_EXCEPTION)
        
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.optimizer = AdamW(self.model.parameters(), lr=self.lr)
        tokenizer = self.model.tokenizer

        # load data
        if self.train_loader is None or self.valid_loader is None:
            # load data
            df_train, df_valid = self.load_data()
            # get labels from data
            self.get_labels(df_train, fl_ctx)
            # create dataloader
            train_dataset = DataSequence(df_train, self.labels_to_ids, tokenizer=tokenizer, ignore_token=self.ignore_token)
            valid_dataset = DataSequence(df_valid, self.labels_to_ids, tokenizer=tokenizer, ignore_token=self.ignore_token)
            self.train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)
            self.valid_loader = DataLoader(valid_dataset, batch_size=self.batch_size, shuffle=False)
            self.log_info(
                fl_ctx,
                f"Num sequence {len(train_dataset)}, Num tokens {len(train_dataset)*150}",
            )

    def local_train(
        self,
        fl_ctx,
        train_loader,
        abort_signal: Signal,
    ):
        """Typical training logic
        Total local epochs: self.aggregation_epochs
        Load data pairs from train_loader
        Compute loss with self.model
        Update model
        """
        for epoch in range(self.aggregation_epochs):
            if abort_signal.triggered:
                return make_reply(ReturnCode.TASK_ABORTED)
            self.model.train()
            epoch_len = len(train_loader)
            self.epoch_global = self.epoch_of_start_time + epoch
            self.log_info(
                fl_ctx,
                f"Local epoch {self.client_id}: {epoch + 1}/{self.aggregation_epochs} (lr={self.lr})",
            )
            avg_loss = 0.0
            for i, batch_data in enumerate(train_loader):
                if abort_signal.triggered:
                    return make_reply(ReturnCode.TASK_ABORTED)
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
            self.log_info(fl_ctx, f"loss of this epoch is {format(avg_loss / len(train_loader))}")

    def local_valid(
        self,
        valid_loader,
        abort_signal: Signal,
        record_epoch=None,
    ):
        """Typical validation logic
        Load data pairs from train_loader
        Compute outputs with model
        Compute evaluation metric with self.valid_metric
        Add score to tensorboard record with specified id
        """
        self.model.eval()
        with torch.no_grad():
            total_acc_val, total_loss_val, val_total = 0, 0, 0
            val_y_pred, val_y_true = [], []
            for val_data, val_label in valid_loader:
                if abort_signal.triggered:
                    return make_reply(ReturnCode.TASK_ABORTED)
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

    def train(
        self,
        shareable: Shareable,
        fl_ctx: FLContext,
        abort_signal: Signal,
    ) -> Shareable:
        """Typical training task pipeline
        Get global model weights (potentially with HE)
        Local training
        Return updated weights (model_diff)
        """
        if abort_signal.triggered:
            return make_reply(ReturnCode.TASK_ABORTED)

        # get round information
        current_round = shareable.get_header(AppConstants.CURRENT_ROUND)
        total_rounds = shareable.get_header(AppConstants.NUM_ROUNDS)
        self.log_info(fl_ctx, f"Current/Total Round: {current_round + 1}/{total_rounds}")
        self.log_info(fl_ctx, f"Client identity: {fl_ctx.get_identity_name()}")

        # update local model weights with received weights
        dxo = from_shareable(shareable)
        global_weights = dxo.data

        # Before loading weights, tensors might need to be reshaped to support HE for secure aggregation.
        local_var_dict = self.model.state_dict()
        model_keys = global_weights.keys()
        for var_name in local_var_dict:
            if var_name in model_keys:
                weights = global_weights[var_name]
                try:
                    # reshape global weights to compute difference later on
                    global_weights[var_name] = np.reshape(weights, local_var_dict[var_name].shape)
                    # update the local dict
                    local_var_dict[var_name] = torch.as_tensor(global_weights[var_name])
                except Exception as e:
                    raise ValueError("Convert weight from {} failed with error: {}".format(var_name, str(e)))
        self.model.load_state_dict(local_var_dict)

        # local steps
        epoch_len = len(self.train_loader)
        self.log_info(fl_ctx, f"Local steps per epoch: {epoch_len}")

        # local train
        self.local_train(
            fl_ctx=fl_ctx,
            train_loader=self.train_loader,
            abort_signal=abort_signal,
        )
        if abort_signal.triggered:
            return make_reply(ReturnCode.TASK_ABORTED)
        self.epoch_of_start_time += self.aggregation_epochs

        # perform valid after local train
        acc = self.local_valid(self.valid_loader, abort_signal)
        if abort_signal.triggered:
            return make_reply(ReturnCode.TASK_ABORTED)
        self.log_info(fl_ctx, f"val_f1_local_model: {acc:.4f}")

        # compute delta model, global model has the primary key set
        local_weights = self.model.state_dict()
        model_diff = {}
        for name in global_weights:
            if name not in local_weights:
                continue
            model_diff[name] = np.subtract(local_weights[name].cpu().numpy(), global_weights[name], dtype=np.float32)
            if np.any(np.isnan(model_diff[name])):
                self.system_panic(f"{name} weights became NaN...", fl_ctx)
                return make_reply(ReturnCode.EXECUTION_EXCEPTION)

        # build the shareable
        dxo = DXO(data_kind=DataKind.WEIGHT_DIFF, data=model_diff)
        dxo.set_meta_prop(MetaKey.NUM_STEPS_CURRENT_ROUND, epoch_len)

        self.log_info(fl_ctx, "Local epochs finished. Returning shareable")
        return dxo.to_shareable()

    def validate(self, shareable: Shareable, fl_ctx: FLContext, abort_signal: Signal) -> Shareable:
        """Typical validation task pipeline
        Get global model weights (potentially with HE)
        Validation on local data
        Return validation F-1 score
        """
        if abort_signal.triggered:
            return make_reply(ReturnCode.TASK_ABORTED)

        # validation on global model
        model_owner = "global_model"

        # update local model weights with received weights
        dxo = from_shareable(shareable)
        global_weights = dxo.data

        # Before loading weights, tensors might need to be reshaped to support HE for secure aggregation.
        local_var_dict = self.model.state_dict()
        model_keys = global_weights.keys()
        n_loaded = 0
        for var_name in local_var_dict:
            if var_name in model_keys:
                weights = torch.as_tensor(global_weights[var_name], device=self.device)
                try:
                    # update the local dict
                    local_var_dict[var_name] = torch.as_tensor(torch.reshape(weights, local_var_dict[var_name].shape))
                    n_loaded += 1
                except Exception as e:
                    raise ValueError("Convert weight from {} failed with error: {}".format(var_name, str(e)))
        self.model.load_state_dict(local_var_dict)
        if n_loaded == 0:
            raise ValueError(f"No weights loaded for validation! Received weight dict is {global_weights}")

        # before_train_validate; other validate types return VALIDATE_TYPE_UNKNOWN
        validate_type = shareable.get_header(AppConstants.VALIDATE_TYPE)
        if validate_type == ValidateType.BEFORE_TRAIN_VALIDATE:
            # perform valid before local train
            global_metric = self.local_valid(
                self.valid_loader,
                abort_signal,
                record_epoch=self.epoch_global,
            )
            if abort_signal.triggered:
                return make_reply(ReturnCode.TASK_ABORTED)
            self.log_info(fl_ctx, f"val_f1_global_model ({model_owner}): {global_metric:.4f}")
            # validation metrics will be averaged with weights at server end for best model record
            metric_dxo = DXO(
                data_kind=DataKind.METRICS,
                data={MetaKey.INITIAL_METRICS: global_metric},
                meta={},
            )
            metric_dxo.set_meta_prop(MetaKey.NUM_STEPS_CURRENT_ROUND, len(self.valid_loader))
            return metric_dxo.to_shareable()
        else:
            return make_reply(ReturnCode.VALIDATE_TYPE_UNKNOWN)
