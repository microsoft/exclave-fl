# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import base64
import json

def base64encode(rawstring: str):
    rawstring_bytes = rawstring.encode("ascii")
    rawstring_base64_bytes = base64.b64encode(rawstring_bytes)
    base64_string = rawstring_base64_bytes.decode('ascii')
    return base64_string

def base64decode(base64_string: str):
    base64_bytes = base64_string.encode('ascii')
    raw_bytes = base64.b64decode(base64_bytes)
    raw_string = raw_bytes.decode('ascii')
    return raw_string