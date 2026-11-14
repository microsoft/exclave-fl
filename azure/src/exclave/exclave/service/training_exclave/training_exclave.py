# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import numpy as np
import torch
import logging

from threading import Thread
from abc import ABC, abstractmethod
from exclave.base.tee_exclave import TeeExclave
from exclave.utils.utils import string_hash, dict_hash, model_serialize, model_deserialize

from exclave.service.training_exclave import training_pb2
from exclave.service.training_exclave import training_pb2_grpc

from exclave.utils.constants import ROOT_HASH_PATH

class TrainingExclave(TeeExclave, training_pb2_grpc.TrainServicer, ABC):

    def __init__(
        self
    ):

        TeeExclave.__init__(self)

        self.model = None
        self.train_loader = None
        self.valid_loader = None
        self.model_diff = {}
        self.epoch_len = None
        self.is_training = False
        self.training_thread = None

    @abstractmethod
    def initialize(self):
        pass

    def get_data_commitment(self, path: str) -> str:
        with open(path, "r") as f:
            data_commitment = f.read()
        return data_commitment
    
    @abstractmethod
    def train(train_loader, global_weights):
        pass

    @abstractmethod
    def valid(valid_loader):
        pass

    def format_input(self, inputs: dict) -> dict:
        model = inputs["model"]
        data_commitment = inputs["data"]
        global_model = dict(sorted(model.items()))
        return {"model": dict_hash(global_model), "data": data_commitment}

    def format_output(self, outputs: dict) -> dict:
        model = outputs["model"]
        return {'model': dict_hash(dict(sorted(model.items())))}

    # load global weight into model
    def load_global_model(self, global_weights):
        local_var_dict = self.model.state_dict()
        for var_name in local_var_dict:
            local_var_dict[var_name] = torch.as_tensor(global_weights[var_name])
        # load weight to model
        self.model.load_state_dict(local_var_dict)

    # return model_diff directly
    def get_model_diff(self, global_weights):
        model_diff = {}
        local_weights = self.model.state_dict()
        for name in global_weights:
            if name not in local_weights:
                continue
            model_diff[name] = local_weights[name].cpu().numpy() - global_weights[name]
            if np.any(np.isnan(model_diff[name])):
                logging.info("%s weights became NaN...", name)
                return False
        return model_diff

    # core training process
    def train_runner(self, global_model):
        # unwrap model
        global_weights = model_deserialize(global_model)
        # format input
        exclave_input = self.format_input({"model": global_weights, "data": self.get_data_commitment(ROOT_HASH_PATH)})
        # load data and model
        self.initialize()
        # load global model
        self.load_global_model(global_weights)
        # pre training validation
        pre_train_val_acc = self.valid(self.valid_loader)
        logging.info("pre training validation metric: %.4f", pre_train_val_acc)
        # core training block
        model_diff = self.train(self.train_loader, global_weights)
        # post training validation
        post_train_val_acc = self.valid(self.valid_loader)
        logging.info("post training validation metric: %.4f", post_train_val_acc)
        # format output
        exclave_output = self.format_output({"model": model_diff})
        # capture io and get attested
        self.capture_io(exclave_input, exclave_output)
        # set output
        self.model_diff = model_serialize(model_diff)
        self.epoch_len = len(self.train_loader)
    
    # grpc method
    def StartTrain(self, request, context):
        """train rpc
        """
        logging.info("Receive start train request from client")
        if self.is_training is True:
            logging.info("Training task already running; request not accepted")
            return training_pb2.Status(received = False)
        # if exclave has no job now
        global_model = request.global_model
        # train in a new thread
        self.is_training = True
        self.training_thread = Thread(target = self.train_runner, args = (global_model, ))
        self.training_thread.start()
        # return true
        return training_pb2.Status(received = True)

    # grpc method
    def GetWeight(self, request, context):
        # No training Result Available - return empty
        if self.model_diff == {}:
            return training_pb2.WeightUpdate(weight_update=self.model_diff)
        # Training Result is available - return model
        else:
            model_diff = self.model_diff
            # reset
            self.model_diff = {}
            self.is_training = False
            self.training_thread.join()
            logging.info("Returning Locally Trained Model")
            return training_pb2.WeightUpdate(weight_update=model_diff,epoch_len=self.epoch_len)

    # grpc method
    def KeepAlive(self, request, context):
        # return true
        return training_pb2.Status(received = True)
