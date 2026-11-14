# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import hashlib
import json
import os

# PCR 11 value (launch measurement) - all zeros for simulation
PCR11_CODE = "0" * 64


def generate_hash(prefix, client_id=None, round_id=None, extra=None):
    """Generate a deterministic hash based on parameters."""
    data = f"{prefix}"
    if client_id is not None:
        data += f"_client{client_id}"
    if round_id is not None:
        data += f"_round{round_id}"
    if extra is not None:
        data += f"_{extra}"
    return hashlib.sha256(data.encode()).hexdigest()


def generate_fl_logs_structured(num_clients=100, num_rounds=10000, output_dir=None):
    """
    Generate synthetic FL logs with proper hash linkage.
    
    Graph structure per round:
    - Each training node takes: previous model + training data → produces gradient
    - Each DP node takes: gradient → produces DP gradient
    - Aggregation takes: all DP gradients → produces aggregated gradients (global_model)
    - Model Update takes: aggregated gradients + previous model → produces new model
    
    Returns structured logs by client/exclave and the final model hash.
    If output_dir is provided, saves logs in per-client folder structure.
    """
    # Organized logs: train_logs[client_id] = [], dp_logs[client_id] = []
    train_logs = {i: [] for i in range(num_clients)}
    dp_logs = {i: [] for i in range(num_clients)}
    agg_logs = []
    mu_logs = []
    
    # Initial model hash (input for round 1)
    prev_model_hash = generate_hash("initial_model")
    
    for round_id in range(num_rounds):
        dp_outputs = []
        
        for client_id in range(num_clients):
            # Training data hash (leaf input - fixed per client, same across all rounds)
            train_data_hash = generate_hash("train_data", client_id)
            
            # Training node output (gradient)
            gradient_hash = generate_hash("gradient", client_id, round_id)
            
            # Training log entry
            train_log = {
                "input": {
                    "model": prev_model_hash,
                    "data": train_data_hash
                },
                "output": {"model": gradient_hash},
                "code": PCR11_CODE
            }
            train_logs[client_id].append(train_log)
            
            # DP node output
            dp_gradient_hash = generate_hash("dp_gradient", client_id, round_id)
            
            # DP log entry
            dp_log = {
                "input": {"local_model": gradient_hash},
                "output": {"noisy_model": dp_gradient_hash},
                "code": PCR11_CODE
            }
            dp_logs[client_id].append(dp_log)
            
            dp_outputs.append(dp_gradient_hash)
        
        # Aggregation output
        agg_output_hash = generate_hash("agg_output", round_id=round_id)
        
        # Aggregation log entry (only DP gradients, no previous model)
        agg_log = {
            "input": [{"model": h} for h in dp_outputs],
            "output": {"global_model": agg_output_hash},
            "code": PCR11_CODE
        }
        agg_logs.append(agg_log)
        
        # Model Update output (new model)
        new_model_hash = generate_hash("model", round_id=round_id)
        
        # Model Update log entry (aggregated gradients + previous model → new model)
        mu_log = {
            "input": {"base_model": prev_model_hash, "model_diff": agg_output_hash},
            "output": {"full_model": new_model_hash},
            "code": PCR11_CODE
        }
        mu_logs.append(mu_log)
        
        # Update previous model for next round
        prev_model_hash = new_model_hash
        
        if (round_id + 1) % 500 == 0 or round_id == 0:
            print(f"  [Data Gen] Round {round_id + 1}/{num_rounds} ({100*(round_id+1)/num_rounds:.1f}%)", flush=True)
    
    # Save to structured folder if specified
    if output_dir:
        save_structured_logs(output_dir, num_clients, num_rounds, 
                           train_logs, dp_logs, agg_logs, mu_logs)
    
    return {
        'train': train_logs,
        'dp': dp_logs,
        'agg': agg_logs,
        'mu': mu_logs
    }, prev_model_hash


def save_structured_logs(output_dir, num_clients, num_rounds, 
                         train_logs, dp_logs, agg_logs, mu_logs):
    """
    Save logs in per-client folder structure.
    
    Structure:
    output_dir/
    ├── site-1/
    │   ├── train/
    │   │   └── site-1-train.log
    │   └── dp/
    │       └── site-1-dp.log
    └── server/
        ├── agg/
        │   └── server-agg.log
        └── mu/
            └── server-mu.log
    """
    print(f"  [Save] Creating folder structure in {output_dir}...")
    
    # Create site folders for each client
    for client_id in range(num_clients):
        site_name = f"site-{client_id + 1}"
        
        # Train exclave
        train_dir = os.path.join(output_dir, site_name, "train")
        os.makedirs(train_dir, exist_ok=True)
        
        # Write training log
        log_path = os.path.join(train_dir, f"{site_name}-train.log")
        with open(log_path, 'w') as f:
            json.dump(train_logs[client_id], f, indent=2)
        
        # DP exclave
        dp_dir = os.path.join(output_dir, site_name, "dp")
        os.makedirs(dp_dir, exist_ok=True)
        
        # Write DP log
        log_path = os.path.join(dp_dir, f"{site_name}-dp.log")
        with open(log_path, 'w') as f:
            json.dump(dp_logs[client_id], f, indent=2)
    
    # Server folder
    # Aggregation exclave
    agg_dir = os.path.join(output_dir, "server", "agg")
    os.makedirs(agg_dir, exist_ok=True)
    
    log_path = os.path.join(agg_dir, "server-agg.log")
    with open(log_path, 'w') as f:
        json.dump(agg_logs, f, indent=2)
    
    # Model Update exclave
    mu_dir = os.path.join(output_dir, "server", "mu")
    os.makedirs(mu_dir, exist_ok=True)
    
    log_path = os.path.join(mu_dir, "server-mu.log")
    with open(log_path, 'w') as f:
        json.dump(mu_logs, f, indent=2)
    
    total_logs = sum(len(v) for v in train_logs.values()) + \
                 sum(len(v) for v in dp_logs.values()) + \
                 len(agg_logs) + len(mu_logs)
    print(f"  [Save] Saved {total_logs} logs to {output_dir}")

