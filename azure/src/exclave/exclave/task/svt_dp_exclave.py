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

import numpy as np
import logging

from exclave.service.dp_exclave.dp_exclave import DpExclave

class SvtDpExclave(DpExclave):
    def __init__(
        self,
        fraction=1,
        epsilon=0.1,
        noise_var=1e+3,
        gamma=1e-4,
        tau=1e-8,
    ):
        """SVT DP Exclave.
        """
        super().__init__()

        self.frac = float(fraction)  # fraction of the model to upload
        self.eps_1 = float(epsilon)
        self.eps_2 = None  # to be derived from eps_1
        self.eps_3 = float(noise_var)
        self.gamma = float(gamma)
        self.tau = float(tau)

    def add_noise(self, model_diff, epoch_len):
        """Add SVT DP Noise

        Args:
            model_diff: model diff of local model
            epoch_len: epoch length during training

        Returns: noisy result.
        """
        logging.info("Start Adding Noise")
        model_diff = model_diff
        
        total_steps = epoch_len

        delta_w = np.concatenate([model_diff[name].ravel() / np.float64(total_steps) for name in sorted(model_diff)])

        # precompute thresholds
        n_upload = np.minimum(np.ceil(np.float64(delta_w.size) * self.frac), np.float64(delta_w.size))

        # eps_1: threshold with noise
        lambda_rho = self.gamma * 2.0 / self.eps_1
        threshold = self.tau + np.random.laplace(scale=lambda_rho)
        # eps_2: query with noise
        self.eps_2 = self.eps_1 * (2.0 * n_upload) ** (2.0 / 3.0)
        lambda_nu = self.gamma * 4.0 * n_upload / self.eps_2
        # selecting weights with additive noise
        accepted, candidate_idx = [], np.arange(delta_w.size)
        _clipped_w = np.abs(np.clip(delta_w, a_min=-self.gamma, a_max=self.gamma))
        while len(accepted) < n_upload:
            nu_i = np.random.laplace(scale=lambda_nu, size=candidate_idx.shape)
            above_threshold = (_clipped_w[candidate_idx] + nu_i) >= threshold
            accepted += candidate_idx[above_threshold].tolist()
            candidate_idx = candidate_idx[~above_threshold]
            logging.info(f"selected {len(accepted)} responses, requested {n_upload}")
        accepted = np.random.choice(accepted, size=np.int64(n_upload))
        # eps_3 return with noise
        noise = np.random.laplace(scale=self.gamma * 2.0 / self.eps_3, size=accepted.shape)
        delta_w[accepted] = np.clip(delta_w[accepted] + noise, a_min=-self.gamma, a_max=self.gamma)
        candidate_idx = list(set(np.arange(delta_w.size)) - set(accepted))
        delta_w[candidate_idx] = 0.0

        # resume original format
        dp_w, _start = {}, 0
        for name in sorted(model_diff):
            if np.ndim(model_diff[name]) == 0:
                dp_w[name] = model_diff[name]
                _start += 1
                continue
            value = delta_w[_start : (_start + model_diff[name].size)]
            dp_w[name] = value.reshape(model_diff[name].shape) * np.float64(total_steps)
            _start += model_diff[name].size

        logging.info("Adding Noise Finished")
        return dp_w