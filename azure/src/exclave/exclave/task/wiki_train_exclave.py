# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
#
# This file is modified from code under the following notice:
#
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
import logging
import numpy as np
import torch
import math
import transformers
import datasets

from itertools import chain
from torch.utils.data import DataLoader
from transformers import default_data_collator
from datasets import load_dataset

from pt.networks.nlp_models import GPTModelCLM 

from exclave.service.training_exclave.training_exclave import TrainingExclave
from exclave.utils.constants import DATA_PATH


class WikiTrainExclave(TrainingExclave):
    def __init__(
        self,
        model_name: str = "gpt2",
        epochs: int = 1,
        lr: float = 5e-5,
        batch_size: int = 32
    ):
        """NLP Training Exclave on Wiki Dataset
        """
        super().__init__()

        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.model_name = model_name

        self.device = None
        self.model = None
        self.optimizer = None
        self.train_dataset = None
        self.valid_dataset = None
        self.train_loader = None
        self.valid_loader = None


    def initialize(self):
        if self.model is None:
            if self.model_name == "gpt2" or self.model_name == "distilgpt2":
                self.model = GPTModelCLM(model_name=self.model_name)
            else:
                raise ValueError(f"Model {self.model_name} is not supported by NLP Exclave.")
        
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=self.lr)
        tokenizer = self.model.tokenizer
        config = self.model.config
      
        # load data
        if self.train_loader is None or self.valid_loader is None:

            data_files = {}
            dataset_args = {}
            data_files["train"] = os.path.join(DATA_PATH, "wiki.train.txt")
            data_files["validation"] = os.path.join(DATA_PATH, "wiki.valid.txt") 
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

            # Concatenate all texts and split them into chunks of block_size.
            def group_texts(examples):
                # Concatenate all texts.
                concatenated_examples = {k: list(chain(*examples[k])) for k in examples.keys()}
                total_length = len(concatenated_examples[list(examples.keys())[0]])
                # Drop the small remainder that does not fill a whole block.
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
            
            # tokens are grouped in 1024
            logging.info(f" Num tokens = {len(train_dataset)*1024}")

            # DataLoaders creation:
            self.train_loader = DataLoader(
                train_dataset, shuffle=True, collate_fn=default_data_collator, batch_size=self.batch_size
            )
            self.valid_loader = DataLoader(
                valid_dataset, collate_fn=default_data_collator, batch_size=self.batch_size
            )


    # nlp training logic
    def train(self, train_loader, global_weights):
        logging.info("Start local training")
        for epoch in range(self.epochs):
            self.model.train()
            avg_loss = 0.0
            # inputs, labels
            for step, batch in enumerate(train_loader):
                batch = {key: value.to(self.device) for key, value in batch.items()}
                outputs = self.model(**batch)
                loss = outputs.loss
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
                avg_loss += loss.item()
            logging.info("loss of this epoch is {}".format(avg_loss / len(train_loader)))
        model_diff = self.get_model_diff(global_weights)
        return model_diff
    
    # nlp validation logic
    def valid(self, valid_loader):
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
