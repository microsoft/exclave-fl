# nvflare-ext

The NVFlare side of ExclaveFL: the `confidential_fl` package and the evaluation jobs. The Azure
scripts are in [`../azure`](../azure) and the exclave services in
[`../azure/src/exclave`](../azure/src/exclave).

- `confidential_fl/` has the shadow executor, the gRPC connectors to the exclaves, the SVT privacy
  filter, the exclave shareable generator and the CVM provisioning builders
  (`lighter/impl/cvm_{enclave,exclave}.py`).
- `examples/evaluation/` has the provisioning projects (`*_fl.yml`), the 12 jobs (`job_upload/`),
  the models and learners (`pt/`), `submit_job.py` and the requirements (`virtualenv/`).
- NVFlare itself is the submodule [`../third_party/NVFlare`](../third_party/NVFlare), at `95ebf6a`
  (2.2.1+60).

## Install locally

On Azure, each image's `prepare.sh` installs everything. For local development, use Python 3.10:

```bash
git clone --recurse-submodules https://github.com/microsoft/exclave-fl
cd exclave-fl/nvflare-ext
pip install ../third_party/NVFlare
pip install .
pip install -r examples/evaluation/virtualenv/cvm-min-requirements.txt
pip install -r examples/evaluation/virtualenv/cvm-torch-requirements.txt --index-url https://download.pytorch.org/whl/cu124
```

## Provision by hand

`prepare.sh` does this inside each image. The project files and the `cvm_*_exclaves` job configs
contain `${DNS_PREFIX}`, so fill it in first:

```bash
cd examples/evaluation
export DNS_PREFIX=""   # as in azure/config.env
envsubst '${DNS_PREFIX}' < cvm_exclave_fl.yml > cvm_exclave_fl.rendered.yml
nvflare provision -p cvm_exclave_fl.rendered.yml
rm -rf job && cp -r job_upload job
for f in job/*/*/config/config_fed_*.json; do envsubst '${DNS_PREFIX}' < "$f" > "$f.tmp" && mv "$f.tmp" "$f"; done
```

The other projects are `vm_vanilla_fl.yml` for NVFlare (No security) and `cvm_enclave_fl.yml` for
NVFlare (CVM).

## Jobs

Each model has a `<model>_baselines` job for the NVFlare (No security) and NVFlare (CVM) flows, and
a `cvm_<model>_exclaves` job for the ExclaveFL flow. The models are `lenet` and `vgg9` (CIFAR-10),
`mobilebert` and `bert` (NCBI-disease), and `gpt2` and `distilgpt2` (WikiText-103). The datasets go
on dm-verity data disks; see [`../azure/confidential-vm/storage`](../azure/confidential-vm/storage).
