# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import json
import logging
import struct

from abc import ABC, abstractmethod
from tpm2_pytss import ESAPI, ESYS_TR, TPM2_ALG, TPML_DIGEST_VALUES, TPMT_HA, TPMT_SIG_SCHEME
from exclave.base.base_exclave import BaseExclave
from exclave.utils.utils import string_hash, dict_hash
from exclave.utils.constants import PCR_LAUNCH_TIME, PCR_RUNTIME

class TeeExclave(BaseExclave, ABC):

    def __init__(self):
        super().__init__()
        # init time measurement of the TEE
        self.launch_measurement = None
        
        # initialize the log file
        f = open("io.json", "w")
        f.write(json.dumps([]))
        f.close()
        f = open("attest.json", "w")
        f.write(json.dumps([]))
        f.close()

        self.ectx = ESAPI()
        # get launch time measurement
        self.get_cvm_launch_measurement()
    
    def get_cvm_launch_measurement(self):
        # get measurement in lower case.
        _, _, pcr_values = self.ectx.pcr_read(f"sha256:{PCR_LAUNCH_TIME}")
        self.launch_measurement = pcr_values.digests[0].buffer.hex()
        logging.info(f"Launch time measurement: {self.launch_measurement}")

    # extend cvm pcr
    def cvm_attest(self, runtime_data: str) -> str:
        # get string hash
        runtime_data_hash = string_hash(runtime_data)
        # before pcr extension
        _, _, pcr_values = self.ectx.pcr_read(f"sha256:{PCR_RUNTIME}")
        logging.info(f"PCR Value before extension: {pcr_values.digests[0].buffer.hex()}")
        logging.info(f"Extending PCR with value: {runtime_data_hash}")
        # extend pcr
        digest = TPMT_HA(hashAlg=TPM2_ALG.SHA256)
        digest.digest.sha256 = bytes.fromhex(runtime_data_hash)
        self.ectx.pcr_extend(getattr(ESYS_TR, f"PCR{PCR_RUNTIME}"), TPML_DIGEST_VALUES(digests=[digest]))
        # print value after extension
        _, _, pcr_values = self.ectx.pcr_read(f"sha256:{PCR_RUNTIME}")
        pcr_value = bytes(pcr_values.digests[0])
        logging.info(f"PCR Value after extension: {pcr_value.hex()}")

        # signing / generate quote, as 'tpm2_quote -c 0x81000003 -l sha256:23 -g sha256'
        ak = self.ectx.tr_from_tpmpublic(0x81000003)
        ak_type = self.ectx.read_public(ak)[0].publicArea.type
        scheme = TPMT_SIG_SCHEME(scheme=TPM2_ALG.RSASSA if ak_type == TPM2_ALG.RSA else TPM2_ALG.ECDSA if ak_type == TPM2_ALG.ECC else TPM2_ALG.HMAC)
        scheme.details.any.hashAlg = TPM2_ALG.SHA256
        quoted, signature = self.ectx.quote(ak, f"sha256:{PCR_RUNTIME}", b"", scheme)

        # write tpm2_quote's default files; the PCR file is TPML_PCR_SELECTION, UINT32 count, TPML_DIGEST
        with open('message_output_file.msg', 'wb') as f:
            f.write(bytes(quoted))
        with open('signature_output_file.sig', 'wb') as f:
            f.write(signature.marshal())
        with open('PCR_output_file.pcrs', 'wb') as f:
            f.write(struct.pack('<IHB4sx', 1, TPM2_ALG.SHA256, 3, (1 << PCR_RUNTIME).to_bytes(4, 'little')).ljust(132, b'\0'))
            f.write(struct.pack('<IIH64s', 1, 1, len(pcr_value), pcr_value).ljust(536, b'\0'))

        # return the runtime data (hash)
        return runtime_data_hash

    # exclave runtime attestation
    def runtime_attest(self, runtime_data: str) -> str:
        return self.cvm_attest(runtime_data)

    # attest and capture io
    def capture_io(self, inputs: str, outputs: str):
        log_data = {"output": outputs, "input": inputs, "code": self.launch_measurement}
        attest_data = {"pcr_value": self.runtime_attest(str(log_data))}
        with open("io.json", "r") as log_file:
            log_file_data = json.load(log_file)
            log_file_data.append(log_data)
        with open("io.json", "w") as log_file:
            json.dump(log_file_data, log_file)
        with open("attest.json", "r") as attest_file:
            attest_file_data = json.load(attest_file)
            attest_file_data.append(attest_data)
        with open("attest.json", "w") as attest_file:
            json.dump(attest_file_data, attest_file)
    
