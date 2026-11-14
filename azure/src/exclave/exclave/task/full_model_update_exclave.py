# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from exclave.service.model_update_exclave.model_update_exclave import ModelUpdateExclave

class FullModelUpdateExclave(ModelUpdateExclave):
    def __init__(
        self,
    ):
        """Model Update Exclave. MODEL DIFF -> FULL MODEL
        """
        super().__init__()

    def model_update(self, base_model, model_diff):
        full_model = dict()
        for layer in base_model:
            if layer not in model_diff:
                full_model[layer] = base_model[layer]
            else:
                full_model[layer] = base_model[layer] + model_diff[layer]
        return full_model  
