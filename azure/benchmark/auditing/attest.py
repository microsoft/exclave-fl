# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging
import hashlib
import json
from pathlib import Path
from datetime import datetime
from time import perf_counter_ns

# --- TPM2-TSS (no spawn) ---
from tpm2_pytss import (
    ESAPI, ESYS_TR, TPM2_ALG, TPM2B_DATA,
    TPML_PCR_SELECTION, TPMS_PCR_SELECTION, TPML_DIGEST_VALUES, TPMT_HA,
    TPMT_SIG_SCHEME, TPMS_ATTEST
)

# --- Cryptography for external signature verification ---
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

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

# --- Helpers to replace tpm2-tools ---

def _pcr_selection(alg: TPM2_ALG, indices):
    """Build a TPML_PCR_SELECTION structure for 'sha256:23'."""
    # build the pcr selection bitmap
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
    """Extend a PCR with a SHA-256 digest."""
    # create hash structure
    ha = TPMT_HA(hashAlg=TPM2_ALG.SHA256)
    # set the digest value in the structure
    ha.digest.sha256 = bytes.fromhex(digest_hex)
    # wrap the digest
    digests = TPML_DIGEST_VALUES(digests=[ha])
    # extend the PCR
    ectx.pcr_extend(getattr(ESYS_TR, f"PCR{pcr_index}"), digests)

def _quote_sha256(ak_handle: int, pcrs, nonce_bytes: bytes):
    # get ak
    ak_tr = ectx.tr_from_tpmpublic(ak_handle)

    # Read AK type (RSA or ECC) to choose the scheme
    out_public, _, _ = ectx.read_public(ak_tr)
    ak_type = out_public.publicArea.type  # TPM2_ALG.RSA or TPM2_ALG.ECC

    # create the signing scheme
    in_scheme = TPMT_SIG_SCHEME()
    if ak_type == TPM2_ALG.RSA:
        in_scheme.scheme = TPM2_ALG.RSASSA
        in_scheme.details.rsassa.hashAlg = TPM2_ALG.SHA256
    elif ak_type == TPM2_ALG.ECC:
        in_scheme.scheme = TPM2_ALG.ECDSA
        in_scheme.details.ecdsa.hashAlg = TPM2_ALG.SHA256
    else:
        raise ValueError(f"Unsupported AK type: {ak_type}")

    # create the pcr selection
    sel = _pcr_selection(TPM2_ALG.SHA256, pcrs)
    # create the nonce
    qualifying = TPM2B_DATA(nonce_bytes)

    # key, pcr selection, nonce, signing scheme
    attest, sig = ectx.quote(ak_tr, sel, qualifying, in_scheme)
    return attest, sig


def compute_expected_pcr(old_pcr_hex: str, extend_data_hex: str) -> str:
    """
    Compute expected PCR value after extension.
    PCR_new = SHA256(PCR_old || extend_data)
    """
    old_pcr_bytes = bytes.fromhex(old_pcr_hex)
    extend_data_bytes = bytes.fromhex(extend_data_hex)
    # extend the hash to replay pcr extension.
    return hashlib.sha256(old_pcr_bytes + extend_data_bytes).hexdigest()


def verify_quote_with_pem(attest_bytes: bytes, sig_bytes: bytes, akpub_pem_path: str,
                          nonce_bytes: bytes, pcr11_before_hex: str,
                          pcr23_before_hex: str, data_hash_hex: str) -> bool:
    """
    Verify a TPM2 quote using the AK public key from a PEM file.

    Step 1 - Verify the signature using the AK public key (external crypto).
    Step 2 - Verify the signed PCR digest matches the expected value.

    Args:
        attest_bytes: Raw attestation blob bytes
        sig_bytes: Raw signature bytes
        akpub_pem_path: Path to AK public key PEM file
        nonce_bytes: Expected nonce
        pcr11_before_hex: PCR 11 value (hex)
        pcr23_before_hex: PCR 23 value before extend (hex)
        data_hash_hex: Hash of extended data (hex)

    Returns True on success, raises on failure.
    """
    # ── Step 1: Signature verification using AK public key ──────────
    # Load the AK public key from PEM file
    with open(akpub_pem_path, "rb") as f:
        akpub = serialization.load_pem_public_key(f.read())
    logging.info(f"Loaded AK public key from {akpub_pem_path}")

    # the TPM signs the raw attestation bytes (not their hash) with RSASSA-PKCS1-v1_5 and SHA-256
    akpub.verify(
        sig_bytes,
        attest_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    logging.info("Step 1 PASSED: Signature is valid (verified with akpub.pem)")

    # ── Step 2: PCR digest verification ─────────────────────────────
    # raw data that is signed by the TPM - includes PCR digest and nonce
    attest_struct, _ = TPMS_ATTEST.unmarshal(attest_bytes)

    # 2a - Nonce check
    extra_data = attest_struct.extraData.buffer
    # TPM-signed nonce vs. expected nonce
    if extra_data != nonce_bytes:
        raise ValueError(
            f"Nonce mismatch: expected {nonce_bytes.hex()}, "
            f"got {extra_data.hex()}"
        )
    logging.info("  Nonce (qualifyingData) matches")

    # 2b - Recompute expected PCR 23 after extend (a remote verifier cannot read the PCRs)
    expected_pcr23_hex = compute_expected_pcr(pcr23_before_hex, data_hash_hex)
    logging.info(f"  Expected PCR 23 after extend: {expected_pcr23_hex}")

    # 2c - Rebuild the composite digest from the known PCR 11 and the computed PCR 23
    pcr_digest_from_quote = attest_struct.attested.quote.pcrDigest.buffer

    # Build expected composite: SHA256(PCR11 || PCR23)
    all_pcr_bytes = bytes.fromhex(pcr11_before_hex) + bytes.fromhex(expected_pcr23_hex)
    expected_composite = hashlib.sha256(all_pcr_bytes).digest()

    logging.info(f"  PCR 11 (launch): {pcr11_before_hex}")
    logging.info(f"  PCR 23 (runtime): {expected_pcr23_hex}")
    logging.info(f"  Expected composite: {expected_composite.hex()}")
    logging.info(f"  Quote has composite: {pcr_digest_from_quote.hex()}")

    # real quote digest (pcr 11 || pcr 23) vs. expected quote digest (pcr 11 || pcr 23)
    if pcr_digest_from_quote != expected_composite:
        raise ValueError(
            f"PCR composite digest mismatch!\n"
            f"  Quote has: {pcr_digest_from_quote.hex()}\n"
            f"  Expected:  {expected_composite.hex()}"
        )
    logging.info("Step 2 PASSED: Signed PCR digest matches expected extend result")
    return True


def cvm_attest(runtime_data: bytes) -> tuple:
    """
    Hash, extend PCR, and quote.
    Returns (latencies, attest, sig, runtime_data_hash)
    where latencies = {'hash': ms, 'extend': ms, 'quote': ms}
    """
    latencies = {}

    # step 1. hashing runtime data
    t0 = perf_counter_ns()
    runtime_data_hash = bytes_hash(runtime_data)
    latencies['hash'] = _ms_since(t0)

    # step 2. extending pcr
    t0 = perf_counter_ns()
    _pcr_extend_sha256(PCR, runtime_data_hash)
    latencies['extend'] = _ms_since(t0)

    # step 3. quoting PCR 11 (launch measurement) and PCR 23 (runtime data)
    t0 = perf_counter_ns()
    attest, sig = _quote_sha256(0x81000003, [11, PCR], NONCE.encode())
    latencies['quote'] = _ms_since(t0)

    return latencies, attest, sig, runtime_data_hash

def export_ak_pubkey_pem(ak_handle: int, output_path: str):
    """Export the AK public key to a PEM file (replaces tpm2_readpublic -f pem)."""
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
    from cryptography.hazmat.backends import default_backend

    # get handle from ak address
    ak_tr = ectx.tr_from_tpmpublic(ak_handle)
    out_public, _, _ = ectx.read_public(ak_tr)

    # read public key from ak public area
    pub_area = out_public.publicArea
    if pub_area.type != TPM2_ALG.RSA:
        raise ValueError(f"expected an RSA AK, got {pub_area.type}")

    # Extract RSA parameters
    n_bytes = bytes(pub_area.unique.rsa)
    n = int.from_bytes(n_bytes, byteorder='big')
    e = pub_area.parameters.rsaDetail.exponent
    if e == 0:
        e = 65537  # TPM default

    # Build RSA public key
    rsa_numbers = RSAPublicNumbers(e, n)
    rsa_pubkey = rsa_numbers.public_key(default_backend())

    # Serialize to PEM
    pem_bytes = rsa_pubkey.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with open(output_path, "wb") as f:
        f.write(pem_bytes)

    logging.info(f"Exported AK public key to {output_path}")


def save_attestation_data(output_dir: str, attest, sig, pcr11_hex: str,
                          pcr23_before_hex: str, data_hash_hex: str, nonce: str):
    """Save attestation data to files for remote verification."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # Save raw bytes
    (out_path / "attest.bin").write_bytes(bytes(attest))
    if sig.sigAlg == TPM2_ALG.RSASSA:
        (out_path / "sig.bin").write_bytes(bytes(sig.signature.rsassa.sig))
    else:
        raise ValueError(f"expected an RSASSA signature, got {sig.sigAlg}")
    
    # Save metadata
    metadata = {
        "pcr11": pcr11_hex,
        "pcr23_before": pcr23_before_hex,
        "data_hash": data_hash_hex,
        "nonce": nonce,
    }
    (out_path / "metadata.json").write_text(json.dumps(metadata, indent=2))
    logging.info(f"Saved attestation data to {output_dir}/")


def verify_quote_from_files(attestation_dir: str, akpub_pem_path: str) -> bool:
    """Load attestation data from files and verify (simulates remote machine)."""
    att_path = Path(attestation_dir)
    
    attest_bytes = (att_path / "attest.bin").read_bytes()
    sig_bytes = (att_path / "sig.bin").read_bytes()
    metadata = json.loads((att_path / "metadata.json").read_text())
    
    logging.info(f"Loaded attestation data from {attestation_dir}/")
    
    return verify_quote_with_pem(
        attest_bytes=attest_bytes,
        sig_bytes=sig_bytes,
        akpub_pem_path=akpub_pem_path,
        nonce_bytes=metadata["nonce"].encode(),
        pcr11_before_hex=metadata["pcr11"],
        pcr23_before_hex=metadata["pcr23_before"],
        data_hash_hex=metadata["data_hash"],
    )


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(MyFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', "%Y-%m-%d %H:%M:%S.%f"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)

    AKPUB_PEM = "akpub.pem"
    ATTESTATION_DIR = "attestation_data"
    TEST_DATA = b"hello world federated learning benchmark"

    # PROVER (CVM): Generate attestation and save to files. Extend PCR 23 and quote PCR 11 and 23.
    logging.info("=== PROVER: Generating attestation ===")
    
    pcr11_before = _pcr_read_hex(11, TPM2_ALG.SHA256)
    pcr23_before = _pcr_read_hex(PCR, TPM2_ALG.SHA256)
    logging.info(f"PCR 11: {pcr11_before}")
    logging.info(f"PCR 23 before: {pcr23_before}")

    latencies, attest, sig, data_hash = cvm_attest(TEST_DATA)

    # Save to files (to be sent to verifier)
    save_attestation_data(ATTESTATION_DIR, attest, sig, pcr11_before, pcr23_before, data_hash, NONCE)
    export_ak_pubkey_pem(0x81000003, AKPUB_PEM)

    logging.info(f"Hash e2e:   {latencies['hash']:.3f} ms")
    logging.info(f"Extend e2e: {latencies['extend']:.3f} ms")
    logging.info(f"Quote e2e:  {latencies['quote']:.3f} ms")

    # VERIFIER (Remote): Load files and verify
    logging.info("")
    logging.info("=== VERIFIER: Verifying from files ===")
    verify_quote_from_files(ATTESTATION_DIR, AKPUB_PEM)
    logging.info("=== Verification complete ===")

