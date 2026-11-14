# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import os
import shutil
import tempfile
import subprocess
import time
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from datasets import load_dataset
from itertools import chain
from torch.utils.data import DataLoader
from transformers import default_data_collator
from exclave.utils.constants import DATA_PATH, DISK_PATH
from exclave.service.data_sanitization_exclave.data_sanitization_exclave import DataSanitizationExclave

# pinned Hugging Face revision (commit hash) of each model
HF_REVISIONS = {
    "ibm-granite/granite-guardian-hap-38m": "faf9291163c7363d4a7ba7fc1dc72243214af931",
}

class HAPDataSanitizationExclave(DataSanitizationExclave):
    def __init__(
        self,
        model_name: str = "ibm-granite/granite-guardian-hap-38m",
        output_file: str = "wiki.train.sanitized.txt"
    ):

        super().__init__()
        self.model_name = model_name
        self.output_file = output_file

    def initialize(self):

        # Check for GPU availability
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name, revision=HF_REVISIONS[self.model_name])
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, revision=HF_REVISIONS[self.model_name])
        
        # Move model to GPU if available
        self.model = self.model.to(self.device)
        
        if self.device.type == "cuda":
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

        # Initialize data_files and dataset_args
        data_files = {}
        dataset_args = {}
        
        data_files["train"] = os.path.join(DATA_PATH, "wiki.train.txt")
        data_files["validation"] = os.path.join(DATA_PATH, "wiki.valid.txt") 
        extension = "text"
        dataset_args["keep_linebreaks"] = True
        raw_datasets = load_dataset(extension, data_files=data_files, **dataset_args)

        # First we tokenize all the texts.
        column_names = raw_datasets["train"].column_names
        text_column_name = "text" if "text" in column_names else column_names[0]
    
        def tokenize_function(examples):
            return self.tokenizer(examples[text_column_name])
    
        tokenized_datasets = raw_datasets.map(
            tokenize_function,
            batched=True,
            remove_columns=column_names,
            desc="Running tokenizer on dataset",
        )
        
        block_size = self.tokenizer.model_max_length
        # Use a reasonable default block size if model_max_length is too large
        if block_size > 1024:
            block_size = 1024
        
        # concatenate all texts and split them into chunks of block_size
        def group_texts(examples):
            # Concatenate all texts.
            concatenated_examples = {k: list(chain(*examples[k])) for k in examples.keys()}
            total_length = len(concatenated_examples[list(examples.keys())[0]])
            # drop the remainder that does not fill a whole block
            total_length = (total_length // block_size) * block_size
            # Split by chunks of max_len.
            result = {
                k: [t[i : i + block_size] for i in range(0, total_length, block_size)]
                for k, t in concatenated_examples.items()
            }
            return result
    
        lm_datasets = tokenized_datasets.map(
            group_texts,
            batched=True,
            desc=f"Grouping texts in chunks of {block_size}",
        )
        
        self.train_tokens = lm_datasets["train"]
        self.valid_tokens = lm_datasets["validation"]

        # Adjust batch size based on device
        if self.device.type == "cuda":
            self.batch_size = 2048  # Larger batch size for GPU
            print("Using GPU - increased batch size to 2048")
        else:
            self.batch_size = 16  # Smaller batch size for CPU
            
        # Use all available CPU cores for data loading
        num_workers = os.cpu_count() or 1
        self.sanitize_loader = DataLoader(
                self.train_tokens, 
                collate_fn=default_data_collator, 
                batch_size=self.batch_size,
                num_workers=num_workers,
                pin_memory=True if self.device.type == "cuda" else False  # Pin memory for GPU
        )

    def sanitize(self):
        
        self.model.eval()
        losses = []
        total_batches = len(self.sanitize_loader)
        print(f"Total batches to process: {total_batches}")
        
        # Track unsafe sequences for removal
        self.unsafe_sequence_indices = []
        self.unsafe_sequences = []  # Store actual unsafe text sequences
        self.unsafe_text_mappings = []  # Store original text for unsafe sequences
        
        # Start timing
        start_time = time.time()
        
        for step, batch in enumerate(self.sanitize_loader):
            batch_start_time = time.time()
            print(f"Processing batch {step + 1}/{total_batches}")
            
            with torch.no_grad():
                # Remove labels from batch for inference
                batch = {k: v for k, v in batch.items() if k != 'labels'}
                
                # Move batch to GPU if available
                batch = {k: v.to(self.device) for k, v in batch.items()}
                
                logits = self.model(**batch).logits
                prediction = torch.argmax(logits, dim=1).detach().cpu().numpy().tolist() # Binary prediction where label 1 indicates toxicity.
                probability = torch.softmax(logits, dim=1).detach().cpu().numpy()[:,1].tolist() #  Probability of toxicity.
                
                # Track unsafe sequences (label 1) and map back to original text
                batch_start_idx = step * self.batch_size
                unsafe_count = 0
                
                # Get the original text for this batch from the dataset
                batch_indices = range(batch_start_idx, min(batch_start_idx + self.batch_size, len(self.train_tokens)))
                batch_texts = [self.train_tokens[i] for i in batch_indices]
                
                for i, pred in enumerate(prediction):
                    if pred == 1:  # Unsafe sequence detected
                        global_idx = batch_start_idx + i
                        self.unsafe_sequence_indices.append(global_idx)
                        
                        # Map back to original text
                        if i < len(batch_texts):
                            # Decode the tokenized text back to readable text
                            original_text = self.tokenizer.decode(batch_texts[i]['input_ids'], skip_special_tokens=True)
                            self.unsafe_text_mappings.append({
                                'index': global_idx,
                                'text': original_text,
                                'probability': probability[i]
                            })
                        
                        unsafe_count += 1
                
                # Calculate batch processing time
                batch_time = time.time() - batch_start_time
                elapsed_time = time.time() - start_time
                
                print(f"Unsafe sequences in this batch: {unsafe_count}")
                print(f"Total unsafe sequences so far: {len(self.unsafe_sequence_indices)}")
                print(f"Batch time: {batch_time:.2f}s | Total elapsed: {elapsed_time:.2f}s")
        
        # Final timing summary
        total_time = time.time() - start_time
        total_sequences = len(self.train_tokens)  # Actual number of sequences processed
        unsafe_percentage = (len(self.unsafe_sequence_indices) / total_sequences) * 100 if total_sequences > 0 else 0
        
        print(f"\n=== SANITIZATION COMPLETE ===")
        print(f"Total processing time: {total_time:.2f}s ({total_time/60:.2f} minutes)")
        print(f"Average time per batch: {total_time/total_batches:.2f}s")
        print(f"Total sequences processed: {total_sequences}")
        print(f"Unsafe sequences detected: {len(self.unsafe_sequence_indices)}")
        print(f"Unsafe percentage: {unsafe_percentage:.2f}%")
        print(f"Safe sequences: {total_sequences - len(self.unsafe_sequence_indices)}")
        

    def get_unsafe_indices(self):
        """Return the list of unsafe sequence indices"""
        return self.unsafe_sequence_indices
    
    def get_unsafe_text_mappings(self):
        """Return the list of unsafe sequences with their original text"""
        return self.unsafe_text_mappings
    
    def save_sanitized_dataset(self) -> bool:
        """Create a sanitized version of the training file by removing unsafe sequences"""

        if (len(self.unsafe_sequence_indices) == 0):
            print("No unsafe sequences found, skipping sanitization")
            return False

        print(f"\n=== CREATING SANITIZED TRAINING FILE ===")
        
        print(f"Removing {len(self.unsafe_sequence_indices)} unsafe sequences from {len(self.train_tokens)} total sequences")
        
        print("Creating sanitized dataset from processed sequences...")
        
        # Create a new dataset with only safe sequences
        unsafe_indices_set = set(self.unsafe_sequence_indices)
        
        # Collect all safe input_ids for batch decoding
        safe_input_ids = []
        for idx, sequence in enumerate(self.train_tokens):
            if idx not in unsafe_indices_set:
                safe_input_ids.append(sequence['input_ids'])
        
        print(f"Batch decoding {len(safe_input_ids)} safe sequences...")
        # Use batch_decode for much faster processing
        safe_sequences = self.tokenizer.batch_decode(safe_input_ids, skip_special_tokens=True)
        
        # Write sanitized file
        print(f"Writing sanitized file to {self.output_file}...")
        with open(self.output_file, 'w', encoding='utf-8') as f:
            # Batched write - much faster than individual writes
            f.write(' '.join(safe_sequences))
        
        # Statistics
        original_count = len(self.train_tokens)
        sanitized_count = len(safe_sequences)
        removed_count = len(unsafe_indices_set)
        removal_percentage = (removed_count / original_count) * 100 if original_count > 0 else 0
        
        print(f"\n=== SANITIZATION COMPLETE ===")
        print(f"Original sequences: {original_count}")
        print(f"Unsafe sequences removed: {removed_count}")
        print(f"Sanitized sequences: {sanitized_count}")
        print(f"Removal percentage: {removal_percentage:.2f}%")
        print(f"Sanitized file saved to: {self.output_file}")

        return True


    def generate_data_commitment(self):
        """Generate a new data commitment for the sanitized dataset"""
        
        print("[!] Starting data commitment generation...")
        
        # Define paths
        verity_device_name = "veritydevice1"
        mount_point_disk = DISK_PATH
        mount_point_data = DATA_PATH
        
        try:
            # Step 0: Copy wiki.valid.txt and wiki.test.txt from /mnt/share before closing dm-verity
            print("[!] Copying wiki.valid.txt and wiki.test.txt from /mnt/share...")
            
            # Copy wiki.valid.txt
            wiki_valid_source = os.path.join(mount_point_data, "wiki.valid.txt")
            wiki_valid_local = "wiki.valid.txt"
            
            if os.path.exists(wiki_valid_source):
                shutil.copy2(wiki_valid_source, wiki_valid_local)
                print(f"[!] Copied {wiki_valid_source} to {wiki_valid_local}")
            else:
                print(f"[!] Warning: {wiki_valid_source} not found")
            
            # Copy wiki.test.txt
            wiki_test_source = os.path.join(mount_point_data, "wiki.test.txt")
            wiki_test_local = "wiki.test.txt"
            
            if os.path.exists(wiki_test_source):
                shutil.copy2(wiki_test_source, wiki_test_local)
                print(f"[!] Copied {wiki_test_source} to {wiki_test_local}")
            else:
                print(f"[!] Warning: {wiki_test_source} not found")
            
            # Step 1: Close/Unmount dm-verity
            print("[!] Closing dm-verity device...")
            
            # Unmount /mnt/share (the dm-verity data mount)
            result = subprocess.run(["umount", mount_point_data], check=False)
            if result.returncode == 0:
                print(f"[!] Unmounted {mount_point_data}")
            else:
                print(f"[!] Warning: Could not unmount {mount_point_data} (return code: {result.returncode})")
            
            # Close the dm-verity device
            result = subprocess.run(["veritysetup", "close", verity_device_name], check=False)
            if result.returncode == 0:
                print(f"[!] Closed dm-verity device {verity_device_name}")
            else:
                print(f"[!] Warning: Could not close dm-verity device (return code: {result.returncode})")
            
            # Unmount /mnt/.disk (the disk partition)
            result = subprocess.run(["umount", mount_point_disk], check=False)
            if result.returncode == 0:
                print(f"[!] Unmounted {mount_point_disk}")
            else:
                print(f"[!] Warning: Could not unmount {mount_point_disk} (return code: {result.returncode})")
            
            print("[!] All dm-verity components closed/unmounted")
            
            # Step 2: Clean the disk partition
            print("[!] Reformatting disk partition...")
            
            # Reformat /dev/sdc1 as ext4 (this wipes all content clean)
            result = subprocess.run(["mkfs.ext4", "-F", "/dev/sdc1"], check=False)
            if result.returncode == 0:
                print("[!] Successfully reformatted /dev/sdc1 as ext4")
            else:
                print(f"[!] Error: Failed to reformat /dev/sdc1 (return code: {result.returncode})")
                raise RuntimeError(f"Failed to reformat disk partition /dev/sdc1")
            
            # Remount the disk
            result = subprocess.run(["mount", "/dev/sdc1", mount_point_disk], check=False)
            if result.returncode == 0:
                print(f"[!] Remounted /dev/sdc1 to {mount_point_disk}")
            else:
                print(f"[!] Error: Failed to remount /dev/sdc1 (return code: {result.returncode})")
                raise RuntimeError(f"Failed to remount /dev/sdc1 to {mount_point_disk}")
            
            print("[!] Disk partition cleaned and remounted")
            
            # Step 3: Create new dm-verity with sanitized data
            print("[!] Creating new dm-verity with sanitized data...")
            
            data_device = "data.img"
            hash_device = "hash.img"
            sanitized_file = self.output_file
            
            # Check if sanitized file exists
            if not os.path.exists(sanitized_file):
                print(f"[!] Error: Sanitized file {sanitized_file} not found")
                raise FileNotFoundError(f"Sanitized file {sanitized_file} does not exist")
            
            # 3.1 Create data device (2GB)
            result = subprocess.run(["truncate", "--size", "2G", data_device], check=False)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to create data device {data_device}")
            print(f"[!] Created {data_device} (2GB)")
            
            # 3.2 Format data device as ext4
            result = subprocess.run(["mkfs.ext4", data_device], check=False)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to format {data_device} as ext4")
            print(f"[!] Formatted {data_device} as ext4")
            
            # 3.3 Mount data device temporarily
            mount_point = tempfile.mkdtemp()
            
            result = subprocess.run(["mount", "-t", "ext4", data_device, mount_point, "-o", "loop"], check=False)
            if result.returncode != 0:
                shutil.rmtree(mount_point, ignore_errors=True)  # Cleanup on failure
                raise RuntimeError(f"Failed to mount {data_device} to {mount_point}")
            print(f"[!] Mounted {data_device} to {mount_point}")
            
            # 3.4 Copy sanitized data into data device
            wiki_train_target = os.path.join(mount_point, "wiki.train.txt")
            shutil.copy2(sanitized_file, wiki_train_target)
            print(f"[!] Copied sanitized data as wiki.train.txt")
            
            # Copy other files if they exist (e.g., wiki.valid.txt, wiki.test.txt)
            wiki_valid_local = "wiki.valid.txt"
            if os.path.exists(wiki_valid_local):
                wiki_valid_target = os.path.join(mount_point, "wiki.valid.txt")
                shutil.copy2(wiki_valid_local, wiki_valid_target)
                print(f"[!] Copied wiki.valid.txt to data device")
            else:
                print(f"[!] Warning: Local wiki.valid.txt not found")
            
            wiki_test_local = "wiki.test.txt"
            if os.path.exists(wiki_test_local):
                wiki_test_target = os.path.join(mount_point, "wiki.test.txt")
                shutil.copy2(wiki_test_local, wiki_test_target)
                print(f"[!] Copied wiki.test.txt to data device")
            else:
                print(f"[!] Warning: Local wiki.test.txt not found")
            
            # List contents for verification
            print(f"[!] Contents of {mount_point}:")
            for item in os.listdir(mount_point):
                item_path = os.path.join(mount_point, item)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    print(f"[!]   {item} ({size} bytes)")
                else:
                    print(f"[!]   {item} (directory)")
            
            # 3.5 Unmount data device
            result = subprocess.run(["umount", mount_point], check=False)
            if result.returncode != 0:
                shutil.rmtree(mount_point, ignore_errors=True)  # Cleanup on failure
                raise RuntimeError(f"Failed to unmount {mount_point}")
            print(f"[!] Unmounted {mount_point}")
            
            # Cleanup temporary directory
            shutil.rmtree(mount_point, ignore_errors=True)
            
            # 3.6 Create dm-verity
            print("[!] Creating dm-verity...")
            result = subprocess.run([
                "veritysetup", "-v", "--debug", "format", 
                data_device, hash_device
            ], capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to create dm-verity: {result.stderr}")
            
            # Extract root hash
            root_hash = None
            for line in result.stdout.split('\n'):
                if 'Root hash:' in line:
                    root_hash = line.split('Root hash:')[1].strip()[-64:]
                    print(f"[!] Root hash: {root_hash}")
                    break
            
            if not root_hash:
                raise RuntimeError("Could not extract root hash from veritysetup output")
            
            # Save root hash
            with open("root_hash", "w") as f:
                f.write(root_hash)
            print(f"[!] Root hash: {root_hash}")
            
            # 3.7 Move files to disk partition
            shutil.move(data_device, mount_point_disk)
            shutil.move(hash_device, mount_point_disk)
            shutil.move("root_hash", mount_point_disk)
            
            print(f"[!] Moved dm-verity files to {mount_point_disk}")
            print(f"[!] Contents of {mount_point_disk}:")
            for item in os.listdir(mount_point_disk):
                item_path = os.path.join(mount_point_disk, item)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    print(f"[!]   {item} ({size} bytes)")
                else:
                    print(f"[!]   {item} (directory)")

            print("[!] New dm-verity created successfully with sanitized data")
 
        except Exception as e:
            print(f"[!] Error during data commitment generation: {e}")
            raise
