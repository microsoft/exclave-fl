# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import numpy as np
import logging

from abc import ABC, abstractmethod
from exclave.base.tee_exclave import TeeExclave
from exclave.utils.utils import string_hash, dict_hash, model_serialize, model_deserialize

from exclave.service.aggregation_exclave import aggregation_pb2
from exclave.service.aggregation_exclave import aggregation_pb2_grpc

class AggregationExclave(TeeExclave, aggregation_pb2_grpc.AggregationServicer, ABC):

    def __init__(
        self
    ):

        TeeExclave.__init__(self)
        self.exclave_input = []
    
    @abstractmethod
    def accept(self, local_model, name, round):
        pass

    @abstractmethod
    def aggregate(self):
        pass

    def format_input(self, inputs: dict) -> dict:
        model = inputs["model"]
        name = inputs["name"]
        return {"model": dict_hash(dict(sorted(model.items()))), "name": name}

    def format_output(self, outputs: dict) -> dict:
        model = outputs["model"]
        return {'global_model': dict_hash(dict(sorted(model.items())))}
    
    # grpc method
    def Accept(self, request, context):
        logging.info("Receive start accept request")
        local_model = model_deserialize(request.local_model)
        contributor_name = request.contributor_name
        contribution_round = request.contribution_round
        accept = self.accept(local_model, contributor_name, contribution_round)
        # if accept -> add log
        if accept:
            self.exclave_input.append(self.format_input({"model": local_model, "name": contributor_name}))
        logging.info("End accept")
        # return whether the model was accepted
        return aggregation_pb2.Accepted(accepted=accept)

    # grpc method
    def Aggregate(self, request, context):
        logging.info("Receive aggregation request")
        aggregation_round = request.aggregation_round
        global_model = self.aggregate()
        exclave_output = self.format_output({"model": global_model})
        global_model = model_serialize(global_model)
        self.capture_io(self.exclave_input, exclave_output)
        # reset input record
        self.exclave_input = []
        logging.info("End aggregation")
        return aggregation_pb2.GlobalModel(global_model=global_model)