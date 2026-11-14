# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

from abc import ABC, abstractmethod

class BaseExclave(ABC):

    def __init__(self):
        pass
    
    @abstractmethod
    def format_input(self, inputs: dict) -> dict:
        pass
    
    @abstractmethod
    def format_output(self, outputs: dict) -> dict:
        pass

    @abstractmethod
    def runtime_attest(self, runtime_data: str) -> str:
        pass

    @abstractmethod
    def capture_io(self, inputs: str, outputs: str):
        pass