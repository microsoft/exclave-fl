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

import os
import pathlib
import shutil

from nvflare.lighter.spec import Builder, Project
from nvflare.lighter.utils import load_yaml
from nvflare.lighter.utils import sh_replace

class CvmExclaveBuilder(Builder):
    def __init__(self, exclave_template_file, config_folder="",):
        """Write the CVM exclave start scripts from the template file into each startup kit."""
        self.exclave_template_file = exclave_template_file
        self.config_folder = config_folder

    def _make_dir(self, dirs):
        for dir in dirs:
            if not os.path.exists(dir):
                os.makedirs(dir)

    def _write(self, file_full_path, content, mode, exe=False):
        mode = mode + "w"
        with open(file_full_path, mode) as f:
            f.write(content)
        if exe:
            os.chmod(file_full_path, 0o755)

    def initialize(self, ctx):
        exclave_template_file_full_path = os.path.join(self.get_resources_dir(ctx), self.exclave_template_file)
        file_path = pathlib.Path(__file__).parent.absolute()
        shutil.copyfile(os.path.join(file_path, self.exclave_template_file), exclave_template_file_full_path)
        ctx["exclave_template_file"] = self.exclave_template_file

        resource_dir = self.get_resources_dir(ctx)
        self.exclave_template_parse = load_yaml(os.path.join(resource_dir, self.exclave_template_file))
        ctx["exclave_template"] = self.exclave_template_parse

    """
    Build Server Start Kit
    1. nvflare_start.sh
    2. nvflare_sub_start.sh
    """
    def _build_server(self, server, client, admin, ctx):
        # dict of startup kit
        dest_dir =  self.get_kit_dir(server, ctx)
        replacement_dict = {
            "admin_name": f"{admin.subject}",
            "server_name": f"{server.subject}",
            "client_name": f"{client.subject}",
            "config_folder": self.config_folder,
        }
        # nvflare_start.sh
        self._write(
            os.path.join(dest_dir, "nvflare_start.sh"),
            sh_replace(self.exclave_template_file["nvflare_start_svr_sh"], replacement_dict),
            "t",
            exe=True,
        )
        # nvflare_sub_start.sh
        self._write(
            os.path.join(dest_dir, "nvflare_sub_start.sh"),
            sh_replace(self.exclave_template_file["nvflare_sub_start_svr_sh"], replacement_dict),
            "t",
            exe=True,
        )

    """
    Build Client Start Kit
    1. nvflare_start.sh
    2. nvflare_sub_start.sh
    """
    def _build_client(self, client, server, ctx):
        # dict of startup kit
        dest_dir =  self.get_kit_dir(client, ctx)
        replacement_dict = {
            "client_name": f"{client.subject}",
            "config_folder": self.config_folder,
            "server_name": f"{server.subject}",
        }
        # nvflare_start.sh
        self._write(
            os.path.join(dest_dir, "nvflare_start.sh"),
            sh_replace(self.exclave_template_file["nvflare_start_cln_sh"], replacement_dict),
            "t",
            exe=True,
        )
        # nvflare_sub_start.sh
        self._write(
            os.path.join(dest_dir, "nvflare_sub_start.sh"),
            sh_replace(self.exclave_template_file["nvflare_sub_start_cln_sh"], replacement_dict),
            "t",
            exe=True,
        )

    def build(self, project, ctx):
        self.exclave_template_file = ctx.get("exclave_template")
        self.project_name = project.name
        self.project = project
        servers = project.get_participants_by_type("server", first_only=False)
        clients = project.get_participants_by_type("client", first_only=False)
        admins = project.get_participants_by_type("admin", first_only=False)
        for server in servers:
            self._build_server(server, clients[0], admins[0], ctx)
        for client in clients:
            self._build_client(client, servers[0], ctx)

