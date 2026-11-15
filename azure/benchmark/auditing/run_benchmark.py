#!/usr/bin/env python3

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Comprehensive FL Attestation Benchmark

Runs end-to-end benchmark for:
  - Synthetic log generation
  - Quote generation (TPM signing)
  - Quote verification
  - Audit graph traversal

Tests combinations of clients [10, 100] and rounds [10, 100, 1000].

Run with: sudo ./env/bin/python run_benchmark.py
"""

import os
import sys
import json
import shutil
from pathlib import Path
from time import perf_counter

# Add script directory to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Direct imports (no subprocess overhead)
from generate_synthetic_data import generate_fl_logs_structured
from quote_generator import generate_all_quotes
from quote_verifier import verify_all_quotes
from audit_scalability_bench import Auditor, load_structured_logs
from attest import export_ak_pubkey_pem

# Benchmark configurations
CLIENTS = [10, 100]
ROUNDS = [10, 100, 1000]

AKPUB_PATH = SCRIPT_DIR / "akpub.pem"


def clean_output_dir(output_dir):
    """Remove output directory if it exists."""
    if output_dir.exists():
        shutil.rmtree(output_dir)


def get_dir_size_mb(dir_path: Path) -> float:
    """Get total size of directory in MB."""
    total = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
    return total / (1024 * 1024)


def run_single_benchmark(clients, rounds):
    """Run benchmark for a single configuration."""
    output_dir = SCRIPT_DIR / f"bench_{clients}x{rounds}"
    results = {
        "clients": clients,
        "rounds": rounds,
        "output_dir": str(output_dir),
    }
    
    print(f"\n{'='*60}")
    print(f"Benchmark: {clients} clients × {rounds} rounds")
    print(f"{'='*60}")

    # Clean up
    clean_output_dir(output_dir)
    
    # Step 1: Generate synthetic logs
    print("\n[1/5] Generating synthetic logs...", end=" ", flush=True)
    t0 = perf_counter()
    try:
        logs, final_model_hash = generate_fl_logs_structured(clients, rounds, str(output_dir))
        elapsed_ms = (perf_counter() - t0) * 1000
        results["log_gen_ms"] = elapsed_ms
        results["log_entries"] = len(logs)
        print(f"✓ ({elapsed_ms:.1f} ms, {len(logs)} entries)")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return results
    
    # Step 2: Generate quotes
    print("[2/5] Generating TPM quotes...", end=" ", flush=True)
    t0 = perf_counter()
    try:
        quote_count = generate_all_quotes(str(output_dir))
        elapsed_ms = (perf_counter() - t0) * 1000
        results["quote_gen_ms"] = elapsed_ms
        results["quotes_generated"] = quote_count
        if quote_count > 0:
            results["quote_gen_per_ms"] = elapsed_ms / quote_count
        print(f"✓ ({elapsed_ms:.1f} ms, {quote_count} quotes)")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return results

    # Step 3: Verify quotes
    print("[3/5] Verifying quotes...", end=" ", flush=True)
    t_verify = perf_counter()
    try:
        verify_results = verify_all_quotes(str(output_dir), str(AKPUB_PATH))
        verify_ms = (perf_counter() - t_verify) * 1000
        results["quote_verify_ms"] = verify_ms
        results["quotes_verified"] = verify_results["verified"]
        results["quotes_failed"] = verify_results["failed"]
        if verify_results["verified"] > 0:
            results["verify_per_ms"] = verify_ms / verify_results["verified"]
        print(f"✓ ({verify_ms:.1f} ms, {verify_results['verified']}/{verify_results['verified'] + verify_results['failed']} verified)")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return results
    
    # Step 4: Audit graph traversal
    print("[4/5] Constructing EDG...", end=" ", flush=True)
    try:
        # graph construction time
        t_construction = perf_counter()
        # Load logs
        log_data, final_model_hash = load_structured_logs(str(output_dir))
        # initialize auditor
        auditor = Auditor()
        # Construct vertices
        vertexs = auditor.construct_vertex(log_data)
        # Construct graph
        auditGraph = auditor.construct_graph(vertexs)
        # measure the graph construction time
        construction_ms = (perf_counter() - t_construction) * 1000
        
        # traverse from the final model's vertex, if found; not part of the benchmark
        if final_model_hash:
            final_vertex = auditor.get_vertex_from_output_and_code(final_model_hash, None, auditGraph)
            if final_vertex:
                inputs = auditor.get_all_input_from_final_vertex(final_vertex, auditGraph)
                results["leaf_inputs"] = len(inputs)
        
        results["vertices"] = len(vertexs)
        results["edges"] = sum(len(edges) for edges in auditGraph.graph.values())
        results["graph_construction_ms"] = construction_ms
        
        print(f"✓ ({construction_ms:.1f} ms, {len(vertexs)} vertices, {results['edges']} edges)")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    # Step 5: Calculate storage overhead
    results["storage_mb"] = get_dir_size_mb(output_dir)
    print(f"[5/5] Storage overhead: {results['storage_mb']:.2f} MB")
    
    # Total time = verify + graph construction
    results["total_ms"] = results.get("quote_verify_ms", 0) + results.get("graph_construction_ms", 0)
    
    return results


def print_summary(all_results: dict):
    """Print summary table."""
    print(f"\n{'='*85}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*85}")
    
    # Header
    print(f"\n{'Config':<12} {'Verify (ms)':<14} {'Construct (ms)':<16} {'Total (ms)':<14} {'Storage (MB)':<14}")
    print(f"{'-'*12} {'-'*14} {'-'*16} {'-'*14} {'-'*14}")
    
    for config, r in all_results.items():
        verify_ms = r.get('quote_verify_ms', 0)
        audit_ms = r.get('graph_construction_ms', 0)
        total_ms = r.get('total_ms', 0)
        storage_mb = r.get('storage_mb', 0)
        
        print(f"{config:<12} {verify_ms:<14.3f} {audit_ms:<16.3f} {total_ms:<14.3f} {storage_mb:<14.2f}")
    
    print(f"\n{'='*85}\n")


def main():
    export_ak_pubkey_pem(0x81000003, str(AKPUB_PATH))
    print("\n" + "="*60)
    print("FL ATTESTATION BENCHMARK")
    print("="*60)
    print(f"Clients: {CLIENTS}")
    print(f"Rounds: {ROUNDS}")
    print(f"Total configurations: {len(CLIENTS) * len(ROUNDS)}")
    
    all_results = {}
    
    for clients in CLIENTS:
        for rounds in ROUNDS:
            config = f"{clients}x{rounds}"
            results = run_single_benchmark(clients, rounds)
            all_results[config] = results
    
    # Print summary
    print_summary(all_results)
    
    # Save results to JSON
    results_file = SCRIPT_DIR / "benchmark_results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Results saved to: {results_file}")


if __name__ == "__main__":
    main()
