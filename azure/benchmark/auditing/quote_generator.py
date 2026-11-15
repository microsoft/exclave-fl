# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Quote Generator for FL Audit Logs

Processes synthetic FL logs and generates TPM quotes for each tuple:
  hash(input, output, code) -> extend PCR 23 -> quote PCR 11 + 23

Processing order (client-centric):
  1. For each client: process train tuples, then dp tuples
  2. Process server agg tuples
  3. Process server mu tuples

Binary output format per quote entry:
  [2 bytes: attest_len][attest_bytes][2 bytes: sig_len][sig_bytes][32 bytes: pcr23_before][32 bytes: data_hash]
"""

import json
import struct
import hashlib
import logging
import argparse
from pathlib import Path

# Reuse TPM operations from attest.py
from attest import (
    ectx, PCR, NONCE,
    _pcr_read_hex, _pcr_extend_sha256, _quote_sha256,
    TPM2_ALG
)

# hash the tuple (input, output, code)
def hash_tuple(log_entry: dict) -> str:
    """
    Hash the (input, output, code) tuple from a log entry.
    Returns hex string of SHA-256 hash.
    """
    # Serialize the tuple deterministically
    tuple_data = json.dumps({
        "input": log_entry.get("input"),
        "output": log_entry.get("output"),
        "code": log_entry.get("code")
    }, sort_keys=True)
    return hashlib.sha256(tuple_data.encode()).hexdigest()

# append the quote to the binary file
def append_quote_to_file(f, attest, sig, pcr23_before_hex: str, data_hash_hex: str):
    """
    Append a quote entry to an open binary file.
    
    Format:
      [2 bytes: attest_len][attest_bytes][2 bytes: sig_len][sig_bytes]
      [32 bytes: pcr23_before][32 bytes: data_hash]
    """
    attest_bytes = bytes(attest)
    
    # Extract signature bytes (RSASSA)
    if sig.sigAlg == TPM2_ALG.RSASSA:
        sig_bytes = bytes(sig.signature.rsassa.sig)
    else:
        raise ValueError(f"expected an RSASSA signature, got {sig.sigAlg}")
    
    # Write length-prefixed attest
    f.write(struct.pack('<H', len(attest_bytes)))
    f.write(attest_bytes)
    
    # Write length-prefixed signature
    f.write(struct.pack('<H', len(sig_bytes)))
    f.write(sig_bytes)
    
    # Write fixed-size PCR and hash values
    f.write(bytes.fromhex(pcr23_before_hex))
    f.write(bytes.fromhex(data_hash_hex))

# hash, extend pcr23, then quote pcr11 + 23.
def sign_log_file(log_path: str, quotes_bin_path: str) -> int:
    """
    Process all tuples in a log file: hash -> extend PCR 23 -> quote.
    Appends quotes to quotes_bin_path.
    
    Returns count of tuples processed.
    """
    with open(log_path, 'r') as f:
        log_entries = json.load(f)
    
    count = 0
    with open(quotes_bin_path, 'ab') as qf:
        for entry in log_entries:
            # Read PCR 23 before extend
            pcr23_before = _pcr_read_hex(PCR, TPM2_ALG.SHA256)
            
            # Hash the tuple
            data_hash = hash_tuple(entry)
            
            # Extend PCR 23
            _pcr_extend_sha256(PCR, data_hash)
            
            # Quote PCR 11 + 23
            attest, sig = _quote_sha256(0x81000003, [11, PCR], NONCE.encode())
            
            # Append to binary file
            append_quote_to_file(qf, attest, sig, pcr23_before, data_hash)
            count += 1
    
    return count


def generate_all_quotes(logs_dir: str) -> int:
    """
    Generate quotes for all log files in the directory structure.
    
    Processing order (client-centric):
      1. For each site: train -> dp
      2. Server: agg -> mu
    
    Returns total count of tuples processed.
    """
    logs_path = Path(logs_dir)
    total_count = 0
    
    # Find all site directories (sorted for deterministic order)
    site_dirs = sorted([d for d in logs_path.iterdir() if d.is_dir() and d.name.startswith('site-')])
    
    # Process each client's logs
    for site_dir in site_dirs:
        # Process train logs
        train_dir = site_dir / 'train'
        if train_dir.exists():
            for log_file in train_dir.glob('*.log'):
                quotes_bin = train_dir / 'quotes.bin'
                logging.info(f"Processing {log_file.name}...")
                count = sign_log_file(str(log_file), str(quotes_bin))
                total_count += count
                logging.info(f"  {count} tuples")
        
        # Process dp logs
        dp_dir = site_dir / 'dp'
        if dp_dir.exists():
            for log_file in dp_dir.glob('*.log'):
                quotes_bin = dp_dir / 'quotes.bin'
                logging.info(f"Processing {log_file.name}...")
                count = sign_log_file(str(log_file), str(quotes_bin))
                total_count += count
                logging.info(f"  {count} tuples")
    
    # Process server logs
    server_dir = logs_path / 'server'
    if server_dir.exists():
        # Process agg logs
        agg_dir = server_dir / 'agg'
        if agg_dir.exists():
            for log_file in agg_dir.glob('*.log'):
                quotes_bin = agg_dir / 'quotes.bin'
                logging.info(f"Processing {log_file.name}...")
                count = sign_log_file(str(log_file), str(quotes_bin))
                total_count += count
                logging.info(f"  {count} tuples")
        
        # Process mu logs
        mu_dir = server_dir / 'mu'
        if mu_dir.exists():
            for log_file in mu_dir.glob('*.log'):
                quotes_bin = mu_dir / 'quotes.bin'
                logging.info(f"Processing {log_file.name}...")
                count = sign_log_file(str(log_file), str(quotes_bin))
                total_count += count
                logging.info(f"  {count} tuples")
    
    return total_count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate TPM quotes for FL audit logs')
    parser.add_argument('--logs-dir', type=str, required=True,
                        help='Directory containing structured FL logs')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    logging.info(f"=== Quote Generator ===")
    logging.info(f"Processing logs from: {args.logs_dir}")
    
    total_count = generate_all_quotes(args.logs_dir)
    
    logging.info(f"=== Done: {total_count} tuples processed ===")
