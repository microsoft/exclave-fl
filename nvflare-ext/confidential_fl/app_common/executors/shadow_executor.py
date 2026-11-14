# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.
#
# This file is modified from code under the following notice:
#
# Copyright (c) 2021-2022, NVIDIA CORPORATION.  All rights reserved.
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

# shadow executor that makes rpc calls to a remote server

from nvflare.apis.dxo import MetaKey, from_shareable
from nvflare.apis.event_type import EventType
from nvflare.apis.executor import Executor
from nvflare.apis.fl_constant import ReturnCode
from nvflare.apis.fl_context import FLContext
from nvflare.apis.shareable import Shareable, make_reply
from nvflare.apis.signal import Signal
from confidential_fl.app_common.abstract.shadow_connector_spec import ShadowConnector
from nvflare.app_common.app_constant import AppConstants, ValidateType
from nvflare.security.logging import secure_format_exception

# Shadow Executor calls Shadow Connector to make the grpc call
class ShadowExecutor(Executor):
    def __init__(
        self,
        remote_task="remote",
        shadow_connector_id = None
    ):
        """Shadow Executor: makes remote procedure calls to a remote rpc server

        Args:
            shadow_connector_id (str): id pointing to the shadow connector object
        """
        super().__init__()
        self.shadow_connector_id = shadow_connector_id

    def handle_event(self, event_type: str, fl_ctx: FLContext):
        if event_type == EventType.START_RUN:
            self.initialize(fl_ctx)
        elif event_type == EventType.END_RUN:
            self.finalize(fl_ctx)

    def initialize(self, fl_ctx: FLContext):
        try:
            engine = fl_ctx.get_engine()
            self.shadow_connector = engine.get_component(self.shadow_connector_id)
            self.shadow_connector.initialize(fl_ctx)
        except Exception as e:
            self.log_exception(fl_ctx, f"learner initialize exception: {secure_format_exception(e)}")

    def execute(self, task_name: str, shareable: Shareable, fl_ctx: FLContext, abort_signal: Signal) -> Shareable:
        self.log_info(fl_ctx, f"Client executor got task: {task_name}")
        result = self.shadow_connector.run(task_name, shareable, fl_ctx, abort_signal)
        # the result is the reply to the server
        return result

    def finalize(self, fl_ctx: FLContext):
        pass
