# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from typing import Union
from time import sleep
import numpy as np
import os

from nvflare.apis.dxo import DXO, DataKind, MetaKey
from nvflare.apis.fl_context import FLContext
from nvflare.apis.shareable import Shareable

from confidential_fl.app_common.abstract.shadow_connector_spec import ShadowConnector

from collections import OrderedDict
import grpc
import io

import confidential_fl.app_common.grpc.model_update.model_update_pb2 as model_update_pb2
import confidential_fl.app_common.grpc.model_update.model_update_pb2_grpc as model_update_pb2_grpc

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

class ModelUpdateConnector(ShadowConnector):
    def __init__(
        self, 
        fqdn = "localhost",
        port = "50051",
    ):
        """Implementation of the connector for converting model from weight_diff to weight
        """

        ShadowConnector.__init__(self)

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


    def get_update(self, base_model, model_diff, fl_ctx: FLContext) -> dict():
        """Call the remote model update exclave
        """
        self.log_debug(fl_ctx, "model_update connector start connection")

        base_model_bytes = numpy_to_bytes(base_model)
        model_diff_bytes = numpy_to_bytes(model_diff)

        full_model = None

        if self.channel is None or self.stub is None:
            self.channel = grpc.insecure_channel(self.remote_url, options=self.grpc_options.items())
            self.stub = model_update_pb2_grpc.ModelUpdateStub(self.channel)

        attempt = 0
        while attempt < MAX_RETRY_ATTEMPT:
            try:
                # submit model_update request
                response = self.stub.ModelUpdate(model_update_pb2.InputModels(base_model=base_model_bytes, model_diff=model_diff_bytes), timeout=TIMEOUT)
                break
            except Exception as e:
                if attempt == MAX_RETRY_ATTEMPT - 1:
                    raise e
                else:
                    self.log_info(fl_ctx, f"Attempt {attempt+1}, grpc exception occurred. Reconnecting.")
                    attempt += 1
                    sleep(10)
        full_model = response.full_model
        # decode full model
        full_model = bytes_to_numpy(full_model)
        return full_model
