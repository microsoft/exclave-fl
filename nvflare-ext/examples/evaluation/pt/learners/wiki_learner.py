# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
#
# This file is modified from code under the following notice:
#
# Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.
# Copyright 2021 The HuggingFace Inc. team. All rights reserved.
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
import torch
import math
import transformers
import datasets

from itertools import chain
from torch.utils.data import DataLoader
from transformers import default_data_collator
from datasets import load_dataset

from nvflare.apis.dxo import DXO, DataKind, MetaKey, from_shareable
from nvflare.apis.fl_constant import FLContextKey, ReturnCode
from nvflare.apis.fl_context import FLContext
from nvflare.apis.shareable import Shareable, make_reply
from nvflare.apis.signal import Signal
from nvflare.app_common.abstract.learner_spec import Learner
from nvflare.app_common.app_constant import AppConstants, ValidateType

from pt.networks.nlp_models import GPTModelCLM

WIKI_ROOT = "/mnt/share"

class WikiLearner(Learner):
    def __init__(
        self,
        learning_rate: float = 5e-5,
        batch_size: int = 32,
        model_name: str = "gpt2",
        aggregation_epochs: int = 1,
    ):
        """Causal Language Modeling Learner.
        """
        super().__init__()
        self.aggregation_epochs = aggregation_epochs
        self.model_name = model_name
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

    def initialize(self, parts: dict, fl_ctx: FLContext):
    
        if self.model is None:
            if self.model_name == "gpt2" or self.model_name == "distilgpt2":
                self.model = GPTModelCLM(model_name=self.model_name)
            else:
                self.system_panic(f"Model {self.model} not supported!", fl_ctx)
                return make_reply(ReturnCode.EXECUTION_EXCEPTION)
        
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=self.lr)
        tokenizer = self.model.tokenizer
        config = self.model.config
      
        # load data
        if self.train_loader is None or self.valid_loader is None:

            data_files = {}
            dataset_args = {}
            data_files["train"] = os.path.join(WIKI_ROOT, "wiki.train.txt")
            data_files["validation"] = os.path.join(WIKI_ROOT, "wiki.valid.txt") 
            extension = "text"
            dataset_args["keep_linebreaks"] = True
            raw_datasets = load_dataset(extension, data_files=data_files, **dataset_args)

            # First we tokenize all the texts.
            column_names = raw_datasets["train"].column_names
            text_column_name = "text" if "text" in column_names else column_names[0]
    
            def tokenize_function(examples):
                return tokenizer(examples[text_column_name])
    
            tokenized_datasets = raw_datasets.map(
                tokenize_function,
                batched=True,
                remove_columns=column_names,
                desc="Running tokenizer on dataset",
            )
        
            block_size = tokenizer.model_max_length
            if block_size > config.max_position_embeddings:
                block_size = min(1024, config.max_position_embeddings)
        
            # concatenate all texts and split them into chunks of block_size
            def group_texts(examples):
                # Concatenate all texts.
                concatenated_examples = {k: list(chain(*examples[k])) for k in examples.keys()}
                total_length = len(concatenated_examples[list(examples.keys())[0]])
                # drop the remainder that does not fill a whole block
                total_length = (total_length // block_size) * block_size
                # Split by chunks of max_len.
                result = {
                    k: [t[i : i + block_size] for i in range(0, total_length, block_size)]
                    for k, t in concatenated_examples.items()
                }
                result["labels"] = result["input_ids"].copy()
                return result
    
            lm_datasets = tokenized_datasets.map(
                group_texts,
                batched=True,
                desc=f"Grouping texts in chunks of {block_size}",
            )
        
            train_dataset = lm_datasets["train"]
            valid_dataset = lm_datasets["validation"]
            
            # Number of Tokens
            self.log_info(fl_ctx, f"Num Token {len(train_dataset)*1024}")
    
            # DataLoaders creation:
            self.train_loader = DataLoader(
                train_dataset, shuffle=True, collate_fn=default_data_collator, batch_size=self.batch_size
            )
            self.valid_loader = DataLoader(
                valid_dataset, collate_fn=default_data_collator, batch_size=self.batch_size
            )


    def local_train(
        self,
        fl_ctx,
        train_loader,
        abort_signal: Signal,
    ):

        for epoch in range(self.aggregation_epochs):
            if abort_signal.triggered:
                return make_reply(ReturnCode.TASK_ABORTED)
            self.model.train()
            self.log_info(
                fl_ctx,
                f"Local epoch {self.client_id}: {epoch + 1}/{self.aggregation_epochs} (lr={self.lr})",
            )
            avg_loss = 0.0
            for step, batch in enumerate(train_loader):
                if abort_signal.triggered:
                    return make_reply(ReturnCode.TASK_ABORTED)
                batch = {key: value.to(self.device) for key, value in batch.items()}
                outputs = self.model(**batch)
                loss = outputs.loss
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
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
        losses = []
        for step, batch in enumerate(valid_loader):
            with torch.no_grad():
                batch = {key: value.to(self.device) for key, value in batch.items()}
                outputs = self.model(**batch)
            loss = outputs.loss
            losses.append(loss.repeat(self.batch_size))
        losses = torch.cat(losses)
        try:
            eval_loss = torch.mean(losses)
            perplexity = math.exp(eval_loss)
        except OverflowError:
            perplexity = float("inf")
        return perplexity

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
        perplexity = self.local_valid(self.valid_loader, abort_signal)
        if abort_signal.triggered:
            return make_reply(ReturnCode.TASK_ABORTED)
        self.log_info(fl_ctx, f"perplexity: local_model: {perplexity:.4f}")

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
        Return validation perplexity
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
            self.log_info(fl_ctx, f"perplexity_global_model ({model_owner}): {global_metric:.4f}")
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
