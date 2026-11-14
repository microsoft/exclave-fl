# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from typing import Union
from time import sleep
import numpy as np
import os

from nvflare.apis.dxo import DXO, DataKind, MetaKey
from nvflare.apis.dxo_filter import DXOFilter
from nvflare.apis.fl_context import FLContext
from nvflare.apis.shareable import Shareable

from confidential_fl.app_common.abstract.shadow_connector_spec import ShadowConnector

from collections import OrderedDict
import grpc
import io

import confidential_fl.app_common.grpc.dp.dp_pb2 as dp_pb2
import confidential_fl.app_common.grpc.dp.dp_pb2_grpc as dp_pb2_grpc

MAX_SEND_MSG_LENGTH = 2147483647
MAX_RECEIVE_MSG_LENGTH = 2147483647

MAX_RETRY_ATTEMPT = 10
TIMEOUT = 300

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

class SvtDpConnector(DXOFilter, ShadowConnector):
    def __init__(
        self, 
        fqdn = "localhost",
        port = "50051",
    ):
        """Implementation of the connector for standard Sparse Vector Technique (SVT) differential privacy
        """
        data_kinds = [DataKind.WEIGHT_DIFF, DataKind.WEIGHTS]

        DXOFilter.__init__(self, supported_data_kinds=[DataKind.WEIGHTS, DataKind.WEIGHT_DIFF], data_kinds_to_filter=data_kinds)
        ShadowConnector.__init__(self)

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
        self.log_info(
            fl_ctx,
            f"Initializing DP Connector"
        )

    # Do not change the API
    def process_dxo(self, dxo: DXO, shareable: Shareable, fl_ctx: FLContext) -> Union[None, DXO]:
        """Call the remote dp exclave

        Args:
            dxo: information from client
            shareable: that the dxo belongs to
            fl_ctx: context provided by workflow

        Returns: filtered result.
        """
        self.log_debug(fl_ctx, "dp connector start connection")
        # numpy dict
        model_diff = dxo.data
        # epoch_len from training
        total_steps = dxo.get_meta_prop(MetaKey.NUM_STEPS_CURRENT_ROUND, 1)
        client_identity = fl_ctx.get_identity_name()
        
        # get exclave domain name
        # each client's exclave is at <client name>-<fqdn>:<port>
        if self.fqdn != "localhost":
            sub_fqdn = str(client_identity) + "-" + self.remote_url
        # fqdn is "localhost": connect to localhost:<port>
        else:
            sub_fqdn = self.remote_url

        self.log_info(fl_ctx, f"Client identity: {client_identity}")
        self.log_info(fl_ctx, f"Get Epoch Len {total_steps}")
        self.log_info(fl_ctx, f"Exclave FQDN {sub_fqdn}")

        model_diff_bytes = numpy_to_bytes(model_diff)

        if self.channel is None or self.stub is None: 
            self.channel = grpc.insecure_channel(sub_fqdn, options=self.grpc_options.items())
            self.stub = dp_pb2_grpc.DifferentialPrivacyStub(self.channel)

        attempt = 0
        while attempt < MAX_RETRY_ATTEMPT:
            try:
                # submit dp request
                response = self.stub.AddNoise(dp_pb2.LocalModel(local_model=model_diff_bytes, epoch_len=total_steps), timeout=TIMEOUT)
                break
            except Exception as e:
                if attempt == MAX_RETRY_ATTEMPT - 1:
                    raise e
                else:
                    self.log_info(fl_ctx, f"Attempt {attempt+1}, grpc exception occurred. Reconnecting.")
                    attempt += 1
                    sleep(10)

        noisy_model = response.noisy_model
        # decode the noisy weight diff (bytes to numpy arrays)
        noisy_model = bytes_to_numpy(noisy_model)

        # build the shareable
        dxo = DXO(data_kind=DataKind.WEIGHT_DIFF, data=noisy_model)
        self.log_info(fl_ctx, "DP add noise finished. Returning dxo")
        return dxo
