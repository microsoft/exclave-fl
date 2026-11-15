# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from __future__ import print_function
from time import sleep

import logging
import random

import copy
import os
import io

import numpy as np

from nvflare.apis.dxo import DXO, DataKind, MetaKey, from_shareable
from nvflare.apis.fl_constant import FLContextKey, ReturnCode
from nvflare.apis.fl_context import FLContext
from nvflare.apis.shareable import ReservedHeaderKey, Shareable, make_reply
from nvflare.apis.signal import Signal
from nvflare.app_common.app_constant import AppConstants
from nvflare.app_common.abstract.learner_spec import Learner
from nvflare.app_common.app_constant import AppConstants, ModelName, ValidateType
from nvflare.app_common.pt.pt_fedproxloss import PTFedProxLoss

from confidential_fl.app_common.abstract.shadow_connector_spec import ShadowConnector

from collections import OrderedDict

import json
import base64
import threading
import grpc


def numpy_to_bytes(arr: np.ndarray) -> bytes:
    """Safely serialize a numpy array to bytes using np.save."""
    buffer = io.BytesIO()
    np.save(buffer, arr, allow_pickle=False)
    return buffer.getvalue()


def bytes_to_numpy(data: bytes) -> np.ndarray:
    """Safely deserialize bytes to a numpy array using np.load."""
    buffer = io.BytesIO(data)
    return np.load(buffer, allow_pickle=False)


import confidential_fl.app_common.grpc.training.training_pb2 as training_pb2
import confidential_fl.app_common.grpc.training.training_pb2_grpc as training_pb2_grpc

MAX_SEND_MSG_LENGTH = 2147483647
MAX_RECEIVE_MSG_LENGTH = 2147483647

MODEL_RETRIEVE_INTERVAL = 0.5
MAX_RETRY_ATTEMPT = 10
TIMEOUT = 10

class TrainingConnector(ShadowConnector): 
    def __init__(
        self,
        fqdn = "localhost",
        port = "50051",
    ):

        super().__init__()

        self.fqdn = fqdn
        self.remote_url = fqdn + ":" + port

        # grpc options
        self.grpc_options = {
            'grpc.max_send_message_length': MAX_SEND_MSG_LENGTH, # max msg length to send
            'grpc.max_receive_message_length': MAX_RECEIVE_MSG_LENGTH, # max msg length to receive
            'grpc.keepalive_time_ms': 120000,  # Send a ping every 120 seconds if no data is sent
            'grpc.keepalive_timeout_ms': 60000,  # 60 seconds timeout for ping acknowledgment
            'grpc.keepalive_permit_without_calls': True,  # Allow pings without active RPC calls
            'grpc.http2.min_ping_interval_without_data_ms': 100000  # Minimum 100 second interval between pings without data
        }

        # grpc connections
        self.channel = None
        self.stub = None

    def initialize(self, fl_ctx: FLContext):
        pass

    def finalize(self, fl_ctx: FLContext):
        pass

    def local_train(self, fl_ctx, train_loader, model_global, abort_signal: Signal, val_freq: int = 0):
        pass

    def save_model(self, is_best=False):
        pass

    def keep_alive(self, interval):
        while True:
            try:
                response = self.stub.KeepAlive(training_pb2.ClientName(client_name="client"), timeout=TIMEOUT)
            except grpc.RpcError as e:
                print(f"An error occurred: {e}")
            sleep(interval)
            
    def run(self, task_name: str, shareable: Shareable, fl_ctx: FLContext, abort_signal: Signal) -> Shareable:
        # Check abort signal
        if abort_signal.triggered:
            return make_reply(ReturnCode.TASK_ABORTED)

        # get round information
        current_round = shareable.get_header(AppConstants.CURRENT_ROUND)
        total_rounds = shareable.get_header(AppConstants.NUM_ROUNDS)
        client_identity = fl_ctx.get_identity_name()
        
        # get exclave domain name
        # each client's exclave is at <client name>-<fqdn>:<port>
        
        if self.fqdn != "localhost":
            sub_fqdn = str(client_identity) + "-" + self.remote_url
        # fqdn is "localhost": connect to localhost:<port>
        else:
            sub_fqdn = self.remote_url
        
        self.log_info(fl_ctx, f"Current/Total Round: {current_round + 1}/{total_rounds}")
        self.log_info(fl_ctx, f"Client identity: {client_identity}")
        self.log_info(fl_ctx, f"Exclave FQDN {sub_fqdn}")

        # update local model weights with received weights
        dxo = from_shareable(shareable)
        global_weights = dxo.data

        global_weights_raw = dict()
        for key in global_weights:
            global_weights_raw[key] = numpy_to_bytes(global_weights[key])

        # create channel if channel does not exist
        if self.channel is None or self.stub is None:
            self.channel = grpc.insecure_channel(sub_fqdn, options=self.grpc_options.items())        
            self.stub = training_pb2_grpc.TrainStub(self.channel)
            self.keep_alive_thread = threading.Thread(target=self.keep_alive, args=(1,))  # Keep alive every 1 second
            self.keep_alive_thread.daemon = True
            self.keep_alive_thread.start()

        # submit training task
        attempt = 0
        while attempt < MAX_RETRY_ATTEMPT:
            try:
                response = self.stub.StartTrain(training_pb2.GlobalModel(global_model=global_weights_raw), timeout=TIMEOUT)
                break
            except Exception as e:
                if attempt == MAX_RETRY_ATTEMPT - 1:
                    raise e
                else:
                    self.log_info(fl_ctx, f"Attempt {attempt+1}, grpc exception {e} occurred. Reconnecting.")
                    attempt += 1
                    sleep(10)
        # retrieve result
        self.weight_update = {}
        self.log_info(fl_ctx, f"Sending Result Retrieve Request to Exclave")

        while len(self.weight_update) < 2:
            try:
                response = self.stub.GetWeight(training_pb2.ClientName(client_name="client"), timeout=TIMEOUT)
                self.weight_update = response.weight_update
                self.epoch_len = response.epoch_len
            except Exception as e:
                self.log_info(fl_ctx, f"GetWeight Request sent. Grpc exception {e} occurred. Reconnecting.")
            if len(self.weight_update) < 2:
                sleep(MODEL_RETRIEVE_INTERVAL)
         
        if abort_signal.triggered:
            return make_reply(ReturnCode.TASK_ABORTED)

        # decode weight diff
        weight_diff = {}
        for key in self.weight_update:
            weight_diff[key] = bytes_to_numpy(self.weight_update[key])
        
        # build the shareable
        dxo = DXO(data_kind=DataKind.WEIGHT_DIFF, data=weight_diff)

        # get epoch_len from grpc response msg, and add it here.
        dxo.set_meta_prop(MetaKey.NUM_STEPS_CURRENT_ROUND, self.epoch_len)
        self.log_info(fl_ctx, f"Set Epoch Len {self.epoch_len}")

        self.log_info(fl_ctx, "Local epochs finished. Returning shareable")
        return dxo.to_shareable()

    def get_model_for_validation(self, model_name: str, fl_ctx: FLContext) -> Shareable:
        pass

    def local_valid(self, valid_loader, abort_signal: Signal, tb_id=None, fl_ctx=None):
        pass

    def validate(self, shareable: Shareable, fl_ctx: FLContext, abort_signal: Signal) -> Shareable:
        pass
