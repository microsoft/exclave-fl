# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging
import hashlib
import os
import time
from datetime import datetime
from time import perf_counter_ns

# --- TPM2-TSS (no spawn) ---
from tpm2_pytss import (
    ESAPI, ESYS_TR, TPM2_ALG, TPM2B_DATA,
    TPML_PCR_SELECTION, TPMS_PCR_SELECTION, TPML_DIGEST_VALUES, TPMT_HA,
    TPMT_SIG_SCHEME
)

PCR=23
NONCE='deadbeef'  # encoded to bytes when used

# Create a single ESAPI context (reused; no spawn)
ectx = ESAPI()  # uses default TCTI (e.g., /dev/tpmrm0)

class MyFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        if not datefmt:
            return super().formatTime(record, datefmt=datefmt)
        return datetime.fromtimestamp(record.created).astimezone().strftime(datefmt)

def _ms_since(start_ns: int) -> float:
    return (perf_counter_ns() - start_ns) / 1e6

def bytes_hash(raw_data: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(raw_data)
    return hasher.hexdigest()

def parse_size(size_spec):
    size_spec = size_spec.lower().strip()
    if size_spec.endswith('k'):
        num = int(size_spec[:-1])
        return num * 1024
    elif size_spec.endswith('m'):
        num = int(size_spec[:-1])
        return num * 1024 * 1024
    elif size_spec.endswith('g'):
        num = int(size_spec[:-1])
        return num * 1024 * 1024 * 1024
    else:
        return int(size_spec)

def generate_data(size_spec):
    byte_size = parse_size(size_spec)
    random_data = os.urandom(byte_size)
    return random_data

# --- Helpers to replace tpm2-tools ---

def _pcr_selection(alg: TPM2_ALG, indices):
    """Build a TPML_PCR_SELECTION like 'sha256:11,23'."""
    pcr_bytes = bytearray(b"\x00\x00\x00")  # PCR 0..23
    for idx in indices:
        byte_i, bit_i = divmod(idx, 8)
        if byte_i >= 3:
            raise ValueError(f"PCR index {idx} is out of range 0..23")
        pcr_bytes[byte_i] |= (1 << bit_i)
    return TPML_PCR_SELECTION(pcrSelections=[
        TPMS_PCR_SELECTION(hash=alg, sizeofSelect=3, pcrSelect=bytes(pcr_bytes))
    ])

def _pcr_read_hex(pcr_index: int, alg: TPM2_ALG = TPM2_ALG.SHA256) -> str:
    sel = _pcr_selection(alg, [pcr_index])
    _, _, pcr_vals = ectx.pcr_read(sel)
    return pcr_vals.digests[0].buffer.hex()

def _pcr_extend_sha256(pcr_index: int, digest_hex: str):
    ha = TPMT_HA(hashAlg=TPM2_ALG.SHA256)
    ha.digest.sha256 = bytes.fromhex(digest_hex)
    digests = TPML_DIGEST_VALUES(digests=[ha])
    ectx.pcr_extend(getattr(ESYS_TR, f"PCR{pcr_index}"), digests)

def _quote_sha256(ak_handle: int, pcrs, nonce_bytes: bytes):
    ak_tr = ectx.tr_from_tpmpublic(ak_handle)

    # Read AK type (RSA or ECC) to choose the scheme
    out_public, _, _ = ectx.read_public(ak_tr)
    ak_type = out_public.publicArea.type  # TPM2_ALG.RSA or TPM2_ALG.ECC

    in_scheme = TPMT_SIG_SCHEME()
    if ak_type == TPM2_ALG.RSA:
        in_scheme.scheme = TPM2_ALG.RSASSA
        in_scheme.details.rsassa.hashAlg = TPM2_ALG.SHA256
    elif ak_type == TPM2_ALG.ECC:
        in_scheme.scheme = TPM2_ALG.ECDSA
        in_scheme.details.ecdsa.hashAlg = TPM2_ALG.SHA256
    else:
        raise ValueError(f"Unsupported AK type: {ak_type}")

    sel = _pcr_selection(TPM2_ALG.SHA256, pcrs)
    qualifying = TPM2B_DATA(nonce_bytes)

    attest, sig = ectx.quote(ak_tr, sel, qualifying, in_scheme)
    return attest, sig


def cvm_attest(runtime_data: bytes) -> list:
    """
    Measures and returns [hash_ms, extend_ms, quote_ms]
    """
    latency = []

    # hash
    logging.info(f"Start Hashing")
    t0 = perf_counter_ns()
    runtime_data_hash = bytes_hash(runtime_data)
    hashing_time = _ms_since(t0)
    logging.info(f"End Hashing")
    latency.append(hashing_time)

    # extend pcr
    logging.info(f"Start Extending PCR")
    t1 = perf_counter_ns()
    _pcr_extend_sha256(PCR, runtime_data_hash)
    extending_time = _ms_since(t1)
    logging.info(f"End Extending PCR")
    latency.append(extending_time)

    # quote
    logging.info(f"Start PCR Quote")
    t2 = perf_counter_ns()
    attest, sig = _quote_sha256(0x81000003, [11, 23], NONCE.encode())  # AK handle and quoted PCRs
    quoting_time = _ms_since(t2)
    logging.info(f"End PCR Quote")
    latency.append(quoting_time)

    # Show results
    # attestation blob in hex
    logging.info("Attestation (hex): %s", bytes(attest).hex())
    # signature depends on key type
    if sig.sigAlg == TPM2_ALG.RSASSA:
        logging.info("Signature (hex): %s", sig.signature.rsassa.sig.buffer.hex())
    elif sig.sigAlg == TPM2_ALG.ECDSA:
        r = sig.signature.ecdsa.signatureR.buffer.hex()
        s = sig.signature.ecdsa.signatureS.buffer.hex()
        logging.info("Signature (ECDSA, r=%s, s=%s)", r, s)
    else:
        logging.info("Signature (alg=%s): %s", sig.sigAlg, sig)


    # return the latencies
    return latency

if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(MyFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', "%Y-%m-%d %H:%M:%S.%f"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

    hash_latency = []
    extend_latency = []
    quote_latency = []

    repeat = 10

    for i in range(repeat):
        data_size = ['1g']
        for size in data_size:

            # generate testing data
            data = generate_data(size)
            time.sleep(5)

            # print value before extension
            before = _pcr_read_hex(PCR, TPM2_ALG.SHA256)
            logging.info(f"PCR Value before extension (sha256:{PCR}): {before}")

            logging.info(f"Start Benchmarking with Data Size {size}")
            latency = cvm_attest(data)
            hash_latency.append(latency[0])
            extend_latency.append(latency[1])
            quote_latency.append(latency[2])

            logging.info(f"End Benchmarking with Data Size {size}")

            # print value after extension
            after = _pcr_read_hex(PCR, TPM2_ALG.SHA256)
            logging.info(f"PCR Value after extension  (sha256:{PCR}): {after}")

    # calculating latencies
    logging.info(f"Hash latency (in ms) {hash_latency}. Average {sum(hash_latency)/len(hash_latency)}")
    logging.info(f"Extend latency (in ms) {extend_latency}. Average {sum(extend_latency)/len(extend_latency)}")
    logging.info(f"Quote latency (in ms) {quote_latency}. Average {sum(quote_latency)/len(quote_latency)}")

