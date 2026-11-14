# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from nvflare.apis.fl_component import FLComponent
from nvflare.apis.fl_context import FLContext
from nvflare.apis.shareable import ReturnCode, Shareable, make_reply
from nvflare.apis.signal import Signal

import logging
import random

import grpc
from confidential_fl.app_common.grpc.utils import base64decode, base64encode

import numpy as np
from collections import OrderedDict

import json
import base64


# serves as grpc client to communicate with remote grpc server
class ShadowConnector(FLComponent):

    def __init__(self):
        """Init the ShadowConnector."""
        FLComponent.__init__(self)

    def initialize(self, fl_ctx: FLContext):
        """Initialize the Shadow Connector object. This could be called to do data preprocessing

        This is called only once.

        Args:
            parts: components to be used by the Connector
            fl_ctx: FLContext of the running environment
        """
        pass

    def run(self, fl_ctx: FLContext):
        """Called to connect to grpc server.

        Args:
            data: the training input data (e.g. model weights)
            fl_ctx: FLContext of the running environment

        """
        pass

    def abort(self, fl_ctx: FLContext):
        """Called (from another thread) to abort the current task (validate or train).

        Note: this is to abort the current task only, not the Connector. After aborting, the Connector
        may still be called to perform another task.

        Args:
            fl_ctx: FLContext of the running environment

        """
        pass

    def finalize(self, fl_ctx: FLContext):
        """Called to finalize the Connector (close/release resources gracefully).

        After this call, the Connector will be destroyed.

        Args:
            fl_ctx: FLContext of the running environment

        """
        pass
