# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import logging

from abc import ABC, abstractmethod
from exclave.base.tee_exclave import TeeExclave
from exclave.utils.utils import string_hash, dict_hash

from exclave.utils.constants import ROOT_HASH_PATH

class DataSanitizationExclave(TeeExclave, ABC):

    def __init__(
        self
    ):

        TeeExclave.__init__(self)

    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def sanitize(self):
        pass

    @abstractmethod
    def save_sanitized_dataset(self) -> bool:
        pass

    @abstractmethod
    def generate_data_commitment(self):
        pass

    def get_data_commitment(self, path: str) -> str:
        with open(path, "r") as f:
            data_commitment = f.read()
        return data_commitment

    def format_input(self, inputs: dict) -> dict:
        data_commitment = inputs["data"]
        return {"data": data_commitment}

    def format_output(self, outputs: dict) -> dict:
        data_commitment = outputs["data"]
        return {'data': data_commitment}

    def sanitizer_runner(self):
        # format input
        logging.info("Start Sanitization")
        logging.info("Start initializing")
        exclave_input = self.format_input({"data": self.get_data_commitment(ROOT_HASH_PATH)})
        # load data and model
        self.initialize()
        logging.info("Finish initializing")
        # sanitize
        logging.info("Start sanitizing dataset")
        self.sanitize()
        logging.info("Finish sanitizing dataset")
        # save sanitized dataset
        new_dataset = self.save_sanitized_dataset()
        # if new dataset is created, generate new data commitment
        if new_dataset is True:
            logging.info("Start generating data commitment")
            self.generate_data_commitment()
            logging.info("Finish generating data commitment")
        # format output
        logging.info("Start formatting output and attestation")
        exclave_output = self.format_output({"data": self.get_data_commitment(ROOT_HASH_PATH)})
        # capture io and get attested
        self.capture_io(exclave_input, exclave_output)
        logging.info("Finish formatting output and attestation")
        logging.info("Sanitization Finished")