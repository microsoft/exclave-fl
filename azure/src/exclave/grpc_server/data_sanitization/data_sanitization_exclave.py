# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import grpc
import logging
from concurrent import futures

from exclave.task.hap_data_sanitization_exclave import HAPDataSanitizationExclave

# Model Name
MODEL_NAME = "ibm-granite/granite-guardian-hap-38m"

if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    exclave = HAPDataSanitizationExclave(model_name=MODEL_NAME)
    exclave.sanitizer_runner()