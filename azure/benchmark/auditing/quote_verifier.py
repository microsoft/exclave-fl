# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Quote Verifier for FL Audit Logs

Verifies TPM quotes from quotes.bin files, simulating remote attestation
where the verifier has no direct TPM access.

Verification steps per quote:
  1. Signature - Verify TPM signature with akpub.pem
  2. Nonce - Check extraData matches expected nonce
  3. PCR Digest - Verify SHA256(PCR11 || PCR23) composite

"""

import json
import struct
import hashlib
import logging
import argparse
from pathlib import Path
from time import perf_counter

from tpm2_pytss import TPMS_ATTEST
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# same nonce as in attest.py
NONCE = 'deadbeef'

# replay pcr extension
def compute_expected_pcr(old_pcr_hex: str, extend_data_hex: str) -> str:
    """
    Compute expected PCR value after extension.
    PCR_new = SHA256(PCR_old || extend_data)
    """
    old_pcr_bytes = bytes.fromhex(old_pcr_hex)
    extend_data_bytes = bytes.fromhex(extend_data_hex)
    return hashlib.sha256(old_pcr_bytes + extend_data_bytes).hexdigest()

# grab the quote from the binary file.
def read_quote_entry(f) -> tuple | None:
    """
    Read one quote entry from binary file.
    
    Returns (attest_bytes, sig_bytes, pcr23_before_hex, data_hash_hex) or None at EOF.
    """
    # Read attest length
    attest_len_bytes = f.read(2)
    if len(attest_len_bytes) < 2:
        return None  # EOF
    attest_len = struct.unpack('<H', attest_len_bytes)[0]
    
    # Read attest bytes
    attest_bytes = f.read(attest_len)
    if len(attest_bytes) < attest_len:
        raise ValueError("Truncated attest data")
    
    # Read sig length
    sig_len_bytes = f.read(2)
    if len(sig_len_bytes) < 2:
        raise ValueError("Truncated sig length")
    sig_len = struct.unpack('<H', sig_len_bytes)[0]
    
    # Read sig bytes
    sig_bytes = f.read(sig_len)
    if len(sig_bytes) < sig_len:
        raise ValueError("Truncated sig data")
    
    # Read fixed-size pcr23_before (32 bytes)
    pcr23_before = f.read(32)
    if len(pcr23_before) < 32:
        raise ValueError("Truncated pcr23_before")
    
    # Read fixed-size data_hash (32 bytes)
    data_hash = f.read(32)
    if len(data_hash) < 32:
        raise ValueError("Truncated data_hash")
    
    return (attest_bytes, sig_bytes, pcr23_before.hex(), data_hash.hex())


def verify_single_quote(attest_bytes: bytes, sig_bytes: bytes, akpub,
                        nonce_bytes: bytes, pcr11_hex: str,
                        pcr23_before_hex: str, data_hash_hex: str) -> str:
    """
    Verify a single quote entry.
    
    Returns the expected PCR 23 value after extend.
    Raises on verification failure.
    """
    # Step 1: Verify signature
    akpub.verify(
        sig_bytes,
        attest_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    # Step 2: Parse attestation and verify contents
    attest_struct, _ = TPMS_ATTEST.unmarshal(attest_bytes)
    
    # 2a: Nonce check
    extra_data = attest_struct.extraData.buffer
    if extra_data != nonce_bytes:
        raise ValueError(f"Nonce mismatch: expected {nonce_bytes.hex()}, got {extra_data.hex()}")
    
    # 2b: Compute expected PCR 23 after extend
    expected_pcr23_hex = compute_expected_pcr(pcr23_before_hex, data_hash_hex)
    
    # 2c: Verify PCR composite digest (PCR11 || PCR23)
    pcr_digest_from_quote = attest_struct.attested.quote.pcrDigest.buffer
    all_pcr_bytes = bytes.fromhex(pcr11_hex) + bytes.fromhex(expected_pcr23_hex)
    expected_composite = hashlib.sha256(all_pcr_bytes).digest()
    
    if pcr_digest_from_quote != expected_composite:
        raise ValueError(
            f"PCR composite mismatch!\n"
            f"  Quote: {pcr_digest_from_quote.hex()}\n"
            f"  Expected: {expected_composite.hex()}"
        )
    
    return expected_pcr23_hex


def verify_quotes(quotes_bin_path: str, log_path: str, akpub_pem_path: str) -> dict:
    """
    Verify all quotes in a binary file against log entries.
    
    Each quote is verified independently, using the PCR 23 value stored with it.
    
    Returns dict with verification results.
    """
    # Load AK public key
    with open(akpub_pem_path, "rb") as f:
        akpub = serialization.load_pem_public_key(f.read())
    
    # Load log entries to get PCR 11 values
    with open(log_path, 'r') as f:
        log_entries = json.load(f)
    
    nonce_bytes = NONCE.encode()
    
    verified = 0
    failed = 0
    
    with open(quotes_bin_path, 'rb') as qf:
        entry_idx = 0
        while True:
            entry = read_quote_entry(qf)
            if entry is None:
                break
            
            attest_bytes, sig_bytes, pcr23_before_hex, data_hash_hex = entry
            
            # Get PCR 11 from log entry's "code" field
            if entry_idx >= len(log_entries):
                raise ValueError(f"More quotes than log entries at index {entry_idx}")
            pcr11_hex = log_entries[entry_idx].get("code", "0" * 64)
            
            try:
                # Verify signature, nonce, and PCR composite
                verify_single_quote(
                    attest_bytes, sig_bytes, akpub, nonce_bytes,
                    pcr11_hex, pcr23_before_hex, data_hash_hex
                )
                verified += 1
            except Exception as e:
                logging.error(f"Entry {entry_idx}: Verification failed - {e}")
                failed += 1
            
            entry_idx += 1
    
    return {
        'verified': verified,
        'failed': failed,
        'total': verified + failed
    }


def verify_all_quotes(logs_dir: str, akpub_pem_path: str) -> dict:
    """
    Verify all quotes in the directory structure.
    
    Returns aggregated verification results.
    """
    logs_path = Path(logs_dir)
    total_results = {
        'verified': 0,
        'failed': 0,
        'files_checked': 0
    }
    
    # Find all site directories
    site_dirs = sorted([d for d in logs_path.iterdir() if d.is_dir() and d.name.startswith('site-')])
    
    # Verify each client's quotes
    for site_dir in site_dirs:
        # Verify train quotes
        train_dir = site_dir / 'train'
        if train_dir.exists():
            quotes_bin = train_dir / 'quotes.bin'
            log_files = list(train_dir.glob('*.log'))
            if quotes_bin.exists() and log_files:
                log_file = log_files[0]
                logging.info(f"Verifying {quotes_bin.relative_to(logs_path)}...")
                result = verify_quotes(str(quotes_bin), str(log_file), akpub_pem_path)
                total_results['verified'] += result['verified']
                total_results['failed'] += result['failed']
                total_results['files_checked'] += 1
        
        # Verify dp quotes
        dp_dir = site_dir / 'dp'
        if dp_dir.exists():
            quotes_bin = dp_dir / 'quotes.bin'
            log_files = list(dp_dir.glob('*.log'))
            if quotes_bin.exists() and log_files:
                log_file = log_files[0]
                logging.info(f"Verifying {quotes_bin.relative_to(logs_path)}...")
                result = verify_quotes(str(quotes_bin), str(log_file), akpub_pem_path)
                total_results['verified'] += result['verified']
                total_results['failed'] += result['failed']
                total_results['files_checked'] += 1
    
    # Verify server quotes
    server_dir = logs_path / 'server'
    if server_dir.exists():
        # Verify agg quotes
        agg_dir = server_dir / 'agg'
        if agg_dir.exists():
            quotes_bin = agg_dir / 'quotes.bin'
            log_files = list(agg_dir.glob('*.log'))
            if quotes_bin.exists() and log_files:
                log_file = log_files[0]
                logging.info(f"Verifying {quotes_bin.relative_to(logs_path)}...")
                result = verify_quotes(str(quotes_bin), str(log_file), akpub_pem_path)
                total_results['verified'] += result['verified']
                total_results['failed'] += result['failed']
                total_results['files_checked'] += 1
        
        # Verify mu quotes
        mu_dir = server_dir / 'mu'
        if mu_dir.exists():
            quotes_bin = mu_dir / 'quotes.bin'
            log_files = list(mu_dir.glob('*.log'))
            if quotes_bin.exists() and log_files:
                log_file = log_files[0]
                logging.info(f"Verifying {quotes_bin.relative_to(logs_path)}...")
                result = verify_quotes(str(quotes_bin), str(log_file), akpub_pem_path)
                total_results['verified'] += result['verified']
                total_results['failed'] += result['failed']
                total_results['files_checked'] += 1
    
    return total_results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verify TPM quotes from FL audit logs')
    parser.add_argument('--logs-dir', type=str, required=True,
                        help='Directory containing FL logs with quotes.bin files')
    parser.add_argument('--akpub', type=str, required=True,
                        help='Path to AK public key PEM file')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    logging.info("=== Quote Verifier ===")
    logging.info(f"Logs directory: {args.logs_dir}")
    logging.info(f"AK public key: {args.akpub}")
    
    t0 = perf_counter()
    results = verify_all_quotes(args.logs_dir, args.akpub)
    elapsed_ms = (perf_counter() - t0) * 1000
    
    logging.info("")
    logging.info("=== Summary ===")
    logging.info(f"Files checked: {results['files_checked']}")
    logging.info(f"Quotes verified: {results['verified']}")
    logging.info(f"Quotes failed: {results['failed']}")
    logging.info(f"Total time: {elapsed_ms:.3f} ms")
    if results['verified'] > 0:
        logging.info(f"Avg per quote: {elapsed_ms / results['verified']:.3f} ms")
    
    if results['failed'] > 0:
        logging.error("VERIFICATION FAILED")
        exit(1)
    else:
        logging.info("ALL QUOTES VERIFIED SUCCESSFULLY")
