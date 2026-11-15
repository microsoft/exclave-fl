# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from __future__ import print_function
from time import sleep

import logging
import random

import copy
import os

import numpy as np

from nvflare.apis.dxo import DXO, DataKind, MetaKey, from_shareable
from nvflare.apis.fl_constant import FLContextKey, ReservedKey, ReturnCode
from nvflare.apis.fl_context import FLContext
from nvflare.apis.shareable import ReservedHeaderKey, Shareable, make_reply
from nvflare.apis.signal import Signal
from nvflare.app_common.app_constant import AppConstants, ModelName, ValidateType

from confidential_fl.app_common.abstract.shadow_connector_spec import ShadowConnector
from nvflare.app_common.abstract.aggregator import Aggregator
from nvflare.app_common.app_constant import AppConstants
from nvflare.app_common.app_event_type import AppEventType

import hashlib
import io

from collections import OrderedDict

import grpc
import confidential_fl.app_common.grpc.aggregation.aggregation_pb2 as aggregation_pb2
import confidential_fl.app_common.grpc.aggregation.aggregation_pb2_grpc as aggregation_pb2_grpc

MAX_SEND_MSG_LENGTH = 2147483647
MAX_RECEIVE_MSG_LENGTH = 2147483647

MAX_RETRY_ATTEMPT = 10
TIMEOUT = 120

def numpy_to_bytes(numpyWeight):
    """Safely serialize a dict of numpy arrays to bytes using np.save."""
    model_keys = numpyWeight.keys()
    bytesweight = dict()
    for key in model_keys:
        buffer = io.BytesIO()
        np.save(buffer, numpyWeight[key], allow_pickle=False)
        bytesweight[key] = buffer.getvalue()
    return bytesweight

def bytes_to_numpy(bytesWeight):
    """Safely deserialize a dict of bytes to numpy arrays using np.load."""
    model_keys = bytesWeight.keys()
    numpyWeight = dict()
    for key in model_keys:
        buffer = io.BytesIO(bytesWeight[key])
        numpyWeight[key] = np.load(buffer, allow_pickle=False)
    return numpyWeight

class AggregationConnector(ShadowConnector, Aggregator):
    def __init__(
        self,
        fqdn = "localhost",
        port = "50051",
    ):

        super().__init__()

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
        self.log_info(
            fl_ctx,
            f"Initializing Server Aggregation Connector"
        )

    def finalize(self, fl_ctx: FLContext):
        pass

    # accept function of aggregator
    def accept(self, shareable: Shareable, fl_ctx: FLContext):

        logging.info("Shadow Agg Connector Accept")
        dxo = from_shareable(shareable)
        contributor_name = shareable.get_peer_prop(key=ReservedKey.IDENTITY_NAME, default="?")
        contribution_round = shareable.get_header(AppConstants.CONTRIBUTION_ROUND)

        rc = shareable.get_return_code()
        if rc and rc != ReturnCode.OK:
            self.log_warning(fl_ctx, f"Contributor {contributor_name} returned rc: {rc}. Disregarding contribution.")
            return False

        local_model = dxo.data
        local_model_bytes = numpy_to_bytes(local_model)

        self.log_info(fl_ctx, f"Server Receive Client {contributor_name}'s Contribution")

        if self.channel is None or self.stub is None:
            self.channel = grpc.insecure_channel(self.remote_url, options=self.grpc_options.items())
            self.stub = aggregation_pb2_grpc.AggregationStub(self.channel)
            
        attempt = 0
        while attempt < MAX_RETRY_ATTEMPT:
            try:
                # submit contribution to aggregator
                response = self.stub.Accept(aggregation_pb2.LocalUpdate(local_model=local_model_bytes, contributor_name=contributor_name, contribution_round=contribution_round), timeout=TIMEOUT)
                break
            except Exception as e:
                if attempt == MAX_RETRY_ATTEMPT - 1:
                    raise e
                else:
                    self.log_info(fl_ctx, f"Attempt {attempt+1}, grpc exception occurred. Reconnecting.")
                    attempt += 1
                    sleep(2)
        # retrieve result
        accepted = response.accepted
        return accepted

    def aggregate(self,fl_ctx: FLContext):

        logging.info("Shadow Agg Connector Aggregate")
        current_round = fl_ctx.get_prop(AppConstants.CURRENT_ROUND)

        global_weight_diff = None

        if self.channel is None or self.stub is None:
            self.channel = grpc.insecure_channel(self.remote_url, options=self.grpc_options.items())
            self.stub = aggregation_pb2_grpc.AggregationStub(self.channel)
        
        attempt = 0
        while attempt < MAX_RETRY_ATTEMPT:
            try:
                # submit aggregation request to aggregator
                response = self.stub.Aggregate(aggregation_pb2.Round(aggregation_round=current_round), timeout=TIMEOUT)
                break
            except Exception as e:
                if attempt == MAX_RETRY_ATTEMPT - 1:
                    raise e
                else:
                    self.log_info(fl_ctx, f"Attempt {attempt+1}, grpc exception occurred. Reconnecting.")
                    attempt += 1
                    sleep(10)

        global_weight_diff = response.global_model
        
        # convert to numpy
        global_weight_diff = bytes_to_numpy(global_weight_diff)
        
        # build the shareable
        dxo = DXO(data_kind=DataKind.WEIGHT_DIFF, data=global_weight_diff)

        self.log_info(fl_ctx, "Aggregation finished. Returning shareable")
        return dxo.to_shareable()
