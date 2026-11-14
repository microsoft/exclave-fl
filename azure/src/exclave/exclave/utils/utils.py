# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import io
import hashlib
import numpy as np
from typing import Dict, List

def dict_hash(dictionary: Dict[str, np.ndarray]) -> str:
    hasher = hashlib.sha256()
    for key, np_array in sorted(dictionary.items()):
        name = key.encode()
        # data type and shape as text, for example "<f4(6, 3, 5, 5)"
        kind = f"{np.lib.format.dtype_to_descr(np_array.dtype)}{np_array.shape}".encode()
        data = np_array.tobytes()
        # each part is hashed with its length in front, so that the parts cannot run together
        for part in (name, kind, data):
            hasher.update(len(part).to_bytes(8, "little"))
            hasher.update(part)
    return hasher.hexdigest()

def string_hash(input_string: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(input_string.encode())
    return hasher.hexdigest()

def model_deserialize(model):
    deserialized_model = dict()
    for key in model:
        buf = io.BytesIO(model[key])
        deserialized_model[key] = np.load(buf, allow_pickle=False)
    return deserialized_model

def model_serialize(model):
    serialized_model = dict()
    for key in model:
        buf = io.BytesIO()
        np.save(buf, model[key], allow_pickle=False)
        serialized_model[key] = buf.getvalue()
    return serialized_model