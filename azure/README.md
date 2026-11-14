# Build and run ExclaveFL on Azure

This guide covers three setups: ExclaveFL ([5](#5-build-and-run-exclavefl)) and two baselines,
NVFlare (CVM) ([6](#6-build-and-run-nvflare-cvm)) and NVFlare (No security)
([7](#7-build-and-run-nvflare-no-security)).

The commands below use `$REPO` for the path of your checkout:

```bash
export REPO=~/exclave-fl
```

## 1. Prerequisites

On your machine (Linux x86-64):

- AzCopy v10, Go 1.18+, Docker with BuildKit (with your user in the `docker` group) and these
  packages:

  ```bash
  sudo apt install -y jq curl gettext-base gdisk cryptsetup cpio binutils rsync git
  ```

- Azure CLI 2.65.0 with the `attestation` extension:

  ```bash
  sudo apt-get install -y --allow-downgrades azure-cli=2.65.0-1~noble    # Ubuntu 22.04: ~jammy
  sudo apt-mark hold azure-cli
  az login
  az extension add --name attestation
  ```

  On Ubuntu 26.04, install
  [`azure-cli_2.65.0-1~noble_amd64.deb`](https://packages.microsoft.com/repos/azure-cli/pool/main/a/azure-cli/azure-cli_2.65.0-1~noble_amd64.deb)
  instead, and run `sudo update-alternatives --set sudo /usr/bin/sudo.ws`.

- The Azure Disk Integrity Tool for Confidential VMs, an Azure CLI extension (`cvm`) that supports
  Azure CLI 2.61–2.66. It is in private preview: access it through its
  [preview page](https://azure.microsoft.com/updates?id=preview-disk-integrity-tool-for-confidential-vms-in-azure),
  then download and install it:

  ```bash
  az extension add --source cvm-0.1.0-py2.py3-none-any.whl
  ```

- An RSA SSH key at `~/.ssh/id_rsa.pub`, and this in `~/.ssh/config`:

  ```
  Host *.westeurope.cloudapp.azure.com
      StrictHostKeyChecking accept-new
  ```

  A new build VM or a rebuilt image comes with new host keys, which `ssh` refuses: remove the old
  ones first with `ssh-keygen -R <host>`.

- About 100 GB of free disk for each image you measure at the same time.

In the [Azure portal](https://portal.azure.com), set up the following in the West Europe region:

- A resource group, with the Owner or Contributor role on it.
- A storage account in that resource group, with shared-key access enabled and the Storage Blob
  Data Contributor role on it.
- A container registry with anonymous pull enabled.
- VM quota (`az vm list-usage -l westeurope -o table`).

## 2. Configure

```bash
cd "$REPO/azure" && cp config.env.example config.env
```

Then fill in `config.env` with your own names, for example:

```bash
RESOURCE_GROUP="exclave-fl-rg"
STORAGE_ACCOUNT="myexclavefl"
GALLERY="exclavefl_gallery"                         # no hyphens; created if missing
IMAGE_VERSION="1.0.0"
DNS_PREFIX="my-"                                    # lowercase, starts with a letter, not with "site"
MAA_NAME="myexclaveflmaa"                           # letters and digits
MAA_ENDPOINT="myexclaveflmaa.weu.attest.azure.net"  # you get it in 3.1
IMAGESERVER="myexclavefl.azurecr.io"                # your container registry
```

## 3. One-time setup

### 3.1 Attestation service (MAA)

```bash
cd "$REPO/azure/confidential-vm/proxy/maa"
source ./set_env.sh
./generate_policy.sh
./create_maa.sh
./sign_policy.sh
./set_policy.sh
```

Put the host name that `set_policy.sh` prints (`MAA Endpoint ...`) into `MAA_ENDPOINT`. Details are
in [maa/README.md](confidential-vm/proxy/maa/README.md). You can also set it up in the
[Azure portal](https://portal.azure.com).

### 3.2 Proxy images

Build `AttestationClient` and the 5 proxy images, and push them to your registry:

```bash
cd "$REPO"
./third_party/cvm-guest-attestation/build.sh
source azure/load-config.sh
az acr login --name <registry>
cd azure/confidential-vm/proxy
for d in enclave-proxy/client enclave-proxy/server exclave-proxy/client exclave-proxy/server exclave-proxy/exclave; do
  (cd "$d/docker" && ./docker-build.sh "$IMAGESERVER") || break
done
for n in cvm-enclave-client-proxy cvm-enclave-server-proxy cvm-exclave-client-proxy cvm-exclave-server-proxy cvm-exclave-proxy; do
  docker push "$IMAGESERVER/$n:latest"
done
```

### 3.3 Data disks

Each of the 4 clients gets its own dm-verity data disk. The datasets are `cifar10` for LeNet and
VGG9, `ncbi` for MobileBERT and BERT, and `wikitext103` for GPT-2 and DistilGPT-2.

1. Create the data-disk VM and the disks, and get the VM's IP:

   ```bash
   cd "$REPO/azure/confidential-vm/storage/deploy-data-disk-vm/verity-data-disk"
   source ./set-env.sh
   export NUM_CLIENTS=4
   ./create-vm.sh
   az vm show -d -g "$AZURE_RESOURCE_GROUP" -n "$DISK_VM_NAME" --query publicIps -o tsv
   ```

2. Ship the code to that VM ([4.2](#42-ship-the-code-to-a-build-vm)) and format the disks on it:

   ```bash
   ssh workspace@<disk-vm-ip>
   cd /home/workspace/exclave-fl/azure/confidential-vm/storage/format-data-disk
   sudo ./verity-format.sh 4 <dataset>
   exit
   ```

3. In the shell of step 1, delete the VM. The disks stay.

   ```bash
   ./stop-and-detach.sh
   ```

## 4. Build an image

Every image is built in the same way. `<dir>` is the image's directory under
`confidential-vm/cvm-os`; sections [5](#5-build-and-run-exclavefl),
[6](#6-build-and-run-nvflare-cvm) and [7](#7-build-and-run-nvflare-no-security) list the images of
each setup.

### 4.1 Build steps

1. Create the build VM and get its IP:

   ```bash
   cd "$REPO/azure/confidential-vm/cvm-os/<dir>/deploy-image-vm"
   source ./set-env.sh
   ./create-vm.sh
   az vm show -d -g "$AZURE_RESOURCE_GROUP" -n "$IMAGE_VM_NAME" --query publicIps -o tsv
   ```

2. Ship the code to it ([4.2](#42-ship-the-code-to-a-build-vm)).
3. Prepare the image on the build VM:

   ```bash
   ssh workspace@<build-vm-ip>
   cd /home/workspace/exclave-fl/azure/confidential-vm/cvm-os/<dir>/prepare-image
   sudo ./upgrade-kernel.sh      # only if <dir> has it; it reboots the VM, so log in again
   sudo ./prepare.sh
   exit
   ```

4. Measure and publish the image, then delete the VHD files and the build VM:

   ```bash
   cd "$REPO/azure/confidential-vm/cvm-os/<dir>/measure-image"
   source ./set-env.sh
   ./measure.sh                  # asks for your sudo password
   ./create-image-version.sh
   ./attestation-policy.sh       # only if <dir> has it
   rm -f reference-os.vhd specialized-os.vhd protected-os.vhd
   az disk revoke-access -g "$AZURE_RESOURCE_GROUP" -n "$IMAGE_VM_DISK_NAME"
   az vm delete -g "$AZURE_RESOURCE_GROUP" -n "$IMAGE_VM_NAME" --yes
   az disk delete -g "$AZURE_RESOURCE_GROUP" -n "$IMAGE_VM_DISK_NAME" --yes
   ```

`measure.sh` downloads the build VM's OS disk, protects it with dm-verity
(`az cvm osdisk integrity-protect`) and writes its measurement, PCR 11, to
`protected-os_measurements.json`. `create-image-version.sh` publishes the protected disk as a
gallery image version, and `attestation-policy.sh` writes the PCR 11 value into the image's
attestation policy.

### 4.2 Ship the code to a build VM

The scripts expect the checkout at `/home/workspace/exclave-fl` on the VM, with the submodules and
your `config.env`. Make a clean clone in a temporary directory (`/tmp/ship`) and copy it over:

```bash
rm -rf /tmp/ship
git clone --recurse-submodules "$REPO" /tmp/ship && cp "$REPO/azure/config.env" /tmp/ship/azure/
rsync -a --exclude .git /tmp/ship/ workspace@<build-vm-ip>:/home/workspace/exclave-fl/
```

## 5. Build and run ExclaveFL

Build these images ([4](#4-build-an-image)):

| Image | `<dir>` |
| --- | --- |
| `<model>`-train-exclave | `exclave/exclave/client/<model>-train` |
| svt-dp-exclave | `exclave/exclave/client/svt-dp` |
| aggregation-exclave | `exclave/exclave/server/aggregation` |
| model-update-exclave | `exclave/exclave/server/model-update` |
| nvflare-client | `exclave/nvflare/client` |
| nvflare-server | `exclave/nvflare/server` |

`<model>` is `lenet`, `vgg9`, `mobilebert`, `bert`, `distilgpt2` or `gpt2`.

Then run an experiment:

```bash
cd "$REPO/azure/confidential-vm/cvm-os/exclave"
./provisioning.sh <run_name> <num_clients>
cd experiments
./deploy.sh <run_name> <num_clients> <model>                     # wait until `pgrep -f deploy-image.sh` prints nothing
./run.sh <run_name> cvm_<model>_exclaves <num_clients> <model>
./status.sh <run_name> <num_clients> <model>                     # done when the server log shows "Finished ScatterAndGather Training."
./result.sh <run_name> <num_clients> <model> <log_dir>
./clean.sh <run_name> <num_clients> <model>                      # wait until `pgrep -f cvm-delete.sh` prints nothing
```

- `<run_name>`: a new name for each run. `<num_clients>`: 1 to 4.
- `<log_dir>`: an existing directory; `result.sh` copies one log per VM into it.
- For H100 clients, add `--gpu` as the last argument of `deploy.sh` and `run.sh`.
- Keep your machine online during a run.

### 5.1 (Optional) Data sanitization

The data-sanitization exclave removes hateful, abusive and profane text from each client's
WikiText-103 data disk with the `ibm-granite/granite-guardian-hap-38m` classifier, and rewrites the
disk with the sanitized text and a new dm-verity root hash. It runs on H100 VMs and needs
`wikitext103` data disks ([3.3](#33-data-disks)).

Build the image data-sanitization-exclave (`<dir>`: `exclave/exclave/client/data-sanitization`),
then run it:

```bash
cd "$REPO/azure/confidential-vm/cvm-os/exclave"
./provisioning.sh <run_name> <num_clients>
cd experiments/data-sanitization
./deploy.sh <run_name> <num_clients> --gpu       # wait until `pgrep -f deploy-image.sh` prints nothing
./run.sh <run_name> <num_clients> --gpu
./status.sh <run_name> <num_clients>             # done when each log shows "Sanitization Finished"
./result.sh <run_name> <num_clients> <log_dir>
./clean.sh <run_name> <num_clients>              # wait until `pgrep -f cvm-delete.sh` prints nothing
```

## 6. Build and run NVFlare (CVM)

This baseline runs each NVFlare client and the NVFlare server in its own CVM. Build these images
([4](#4-build-an-image)):

| Image | `<dir>` |
| --- | --- |
| enclave-client | `enclave/client` |
| enclave-server | `enclave/server` |

**Build enclave-client before enclave-server, and rebuild enclave-server whenever you rebuild
enclave-client.** For enclave-server, also run `./upload-policy.sh <build-vm-ip>` in the shell of
step 1 of [4.1](#41-build-steps), before step 3.

Then run an experiment, with the arguments of [5](#5-build-and-run-exclavefl):

```bash
cd "$REPO/azure/confidential-vm/cvm-os/enclave"
./provisioning.sh <run_name> <num_clients>
cd experiments
./deploy.sh <run_name> <num_clients>                 # wait until `pgrep -f deploy-image.sh` prints nothing
./run.sh <run_name> <model>_baselines <num_clients>
./status.sh <run_name> <num_clients>                 # done when the server log shows "Finished ScatterAndGather Training."
./result.sh <run_name> <num_clients> <log_dir>
./clean.sh <run_name> <num_clients>                  # wait until `pgrep -f cvm-delete.sh` prints nothing
```

This setup uses the same data disks as ExclaveFL, so run one of them at a time.

## 7. Build and run NVFlare (No security)

This baseline runs NVFlare in ordinary VMs. It does not need the attestation service
([3.1](#31-attestation-service-maa)) or the proxy images ([3.2](#32-proxy-images)).

1. Build the image `vanilla/server` ([4](#4-build-an-image)), with `./dump-image.sh` in place of
   `./measure.sh`.
2. Create its data disks as in [3.3](#33-data-disks), but in
   `storage/deploy-data-disk-vm/vanilla-data-disk` and with `sudo ./vanilla-format.sh 4 <dataset>`.
3. Run an experiment, with the arguments of [5](#5-build-and-run-exclavefl):

   ```bash
   cd "$REPO/azure/confidential-vm/cvm-os/vanilla"
   ./provisioning.sh <run_name> <num_clients>
   cd experiments
   ./deploy.sh <run_name> <num_clients>                 # wait until `pgrep -f deploy-image.sh` prints nothing
   ./run.sh <run_name> <model>_baselines <num_clients>
   ./status.sh <run_name> <num_clients>                 # done when the server log shows "Finished ScatterAndGather Training."
   ./result.sh <run_name> <num_clients> <log_dir>
   ./clean.sh <run_name> <num_clients>                  # wait until `pgrep -f cvm-delete.sh` prints nothing
   ```

## 8. Reproducing the paper's results

The experiments in the paper ran in West Europe on:

- CPU VMs (`DCasv5`, `ECasv5`, `Dasv5` and `Easv5`): AMD EPYC 7763.
- GPU VMs (`NCC40ads_H100_v5` and `NC40ads_H100_v5`): AMD EPYC 9V84, and NVIDIA H100 with driver
  550 and CUDA 12.4.

> **Before a run, check the CPU of your VMs (`lscpu`) and make sure that all CPU VMs run on the
> AMD EPYC 7763.** Azure documents this processor for the
> [DCasv5 series](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/dcasv5-series?tabs=sizebasic),
> and it is what our evaluation used. Since recently, we notice that deployments in West Europe
> sometimes land on other processors, such as the AMD EPYC 9V74. This makes the CPUs inconsistent
> between VMs, and the newer processors also show larger placement noise on `DCasv5` VMs.
