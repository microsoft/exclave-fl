# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import numpy as np
import logging

from abc import ABC, abstractmethod
from exclave.base.tee_exclave import TeeExclave
from exclave.utils.utils import string_hash, dict_hash, model_serialize, model_deserialize

from exclave.service.dp_exclave import dp_pb2
from exclave.service.dp_exclave import dp_pb2_grpc

class DpExclave(TeeExclave, dp_pb2_grpc.DifferentialPrivacyServicer, ABC):

    def __init__(
        self
    ):

        TeeExclave.__init__(self)
    
    @abstractmethod
    def add_noise(self, local_model, epoch_len):
        pass

    def format_input(self, inputs: dict) -> dict:
        model = inputs["model"]
        return {"local_model": dict_hash(dict(sorted(model.items())))}

    def format_output(self, outputs: dict) -> dict:
        model = outputs["model"]
        return {'noisy_model': dict_hash(dict(sorted(model.items())))}
    
    # grpc method
    def AddNoise(self, request, context):
        logging.info("Starting DP")
        local_weight = model_deserialize(request.local_model)
        epoch_len = request.epoch_len
        exclave_input = self.format_input({"model": local_weight})
        # adding dp noise
        noisy_model = self.add_noise(local_weight, epoch_len)
        exclave_output = self.format_output({"model": noisy_model})
        noisy_model = model_serialize(noisy_model)
        # capture io and get attested
        self.capture_io(exclave_input, exclave_output)
        return dp_pb2.NoisyModel(noisy_model=noisy_model)
