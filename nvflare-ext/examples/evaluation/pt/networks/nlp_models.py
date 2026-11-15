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

import torch
from transformers import AutoModelForTokenClassification, AutoModelForCausalLM, AutoTokenizer, AutoConfig

# pinned Hugging Face revision (commit hash) of each model
HF_REVISIONS = {
    "bert-base-uncased": "86b5e0934494bd15c9632b12f734a8a67f723594",
    "google/mobilebert-uncased": "1f90a6c24c7879273a291d34a849033eba2dbc0f",
    "gpt2": "607a30d783dfa663caf39e06633721c8d4cfcd7e",
    "distilgpt2": "2290a62682d06624634c1f46a6ad5be0f47f38aa",
}

##################################
# Models for token classification #
##################################

class BertModel(torch.nn.Module):
    def __init__(self, model_name, num_labels):
        super(BertModel, self).__init__()
        self.num_labels = num_labels
        self.model_name = model_name
        self.model = AutoModelForTokenClassification.from_pretrained(
            self.model_name, num_labels=self.num_labels, output_attentions=False, output_hidden_states=False,
            revision=HF_REVISIONS[self.model_name],
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, revision=HF_REVISIONS[self.model_name])

    def forward(self, input_id, mask, label):
        output = self.model(input_ids=input_id, attention_mask=mask, labels=label, return_dict=False)
        return output

# gpt2 model for token classification
class GPTModelTC(torch.nn.Module):
    def __init__(self, model_name, num_labels):
        super(GPTModelTC, self).__init__()
        self.num_labels = num_labels
        self.model_name = model_name
        self.model = AutoModelForTokenClassification.from_pretrained(
            self.model_name,
            num_labels=self.num_labels,
            output_attentions=False,
            output_hidden_states=False,
            revision=HF_REVISIONS[self.model_name],
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, add_prefix_space=True, revision=HF_REVISIONS[self.model_name])
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model.config.pad_token_id = self.model.config.eos_token_id
        self.model.resize_token_embeddings(len(self.tokenizer))

    def forward(self, input_id, mask, label):
        output = self.model(input_ids=input_id, attention_mask=mask, labels=label, return_dict=False)
        return output

# model name: "google/mobilebert-uncased"
class MobileBertModel(torch.nn.Module):
    def __init__(self, model_name, num_labels):
        super(MobileBertModel, self).__init__()
        self.num_labels = num_labels
        self.model_name = model_name
        self.model = AutoModelForTokenClassification.from_pretrained(
            self.model_name, num_labels=self.num_labels, output_attentions=False, output_hidden_states=False,
            revision=HF_REVISIONS[self.model_name],
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, revision=HF_REVISIONS[self.model_name])

    def forward(self, input_id, mask, label):
        output = self.model(input_ids=input_id, attention_mask=mask, labels=label, return_dict=False)
        return output

#######################################
# Models for Causal Language Modeling #
#######################################

# gpt2 model for causal language modeling
class GPTModelCLM(torch.nn.Module):
    def __init__(self, model_name):
        super(GPTModelCLM, self).__init__()
        self.model_name = model_name
        self.config = AutoConfig.from_pretrained(self.model_name, revision=HF_REVISIONS[self.model_name])
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            config=self.config,
            revision=HF_REVISIONS[self.model_name],
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, revision=HF_REVISIONS[self.model_name])
        self.model.resize_token_embeddings(len(self.tokenizer))

    def forward(self, input_ids, attention_mask, labels):
        output = self.model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
        return output
