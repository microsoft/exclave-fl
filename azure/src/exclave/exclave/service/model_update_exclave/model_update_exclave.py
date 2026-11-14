# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import numpy as np
import logging

from abc import ABC, abstractmethod
from exclave.base.tee_exclave import TeeExclave
from exclave.utils.utils import string_hash, dict_hash, model_serialize, model_deserialize

from exclave.service.model_update_exclave import model_update_pb2
from exclave.service.model_update_exclave import model_update_pb2_grpc

class ModelUpdateExclave(TeeExclave, model_update_pb2_grpc.ModelUpdateServicer, ABC):

    def __init__(
        self
    ):

        TeeExclave.__init__(self)
    
    @abstractmethod
    def model_update(self, base_model, model_diff):
        pass

    def format_input(self, inputs: dict) -> dict:
        base_model = inputs["base_model"]
        model_diff = inputs["model_diff"]
        return {"base_model": dict_hash(dict(sorted(base_model.items()))), "model_diff": dict_hash(dict(sorted(model_diff.items())))}

    def format_output(self, outputs: dict) -> dict:
        model = outputs["full_model"]
        return {'full_model': dict_hash(dict(sorted(model.items())))}
    
    # grpc method
    def ModelUpdate(self, request, context):
        logging.info("Starting Model Update")
        base_model = model_deserialize(request.base_model)
        model_diff = model_deserialize(request.model_diff)
        exclave_input = self.format_input({"base_model": base_model, "model_diff": model_diff})
        # update model
        full_model = self.model_update(base_model, model_diff)
        exclave_output = self.format_output({"full_model": full_model})
        full_model = model_serialize(full_model)
        # capture io and get attested
        self.capture_io(exclave_input, exclave_output)
        logging.info("Model Update Finished")
        return model_update_pb2.FullModel(full_model=full_model)
