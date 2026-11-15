# CVM guest attestation (patched)

Our patches to Azure's
[confidential-computing-cvm-guest-attestation](https://github.com/Azure/confidential-computing-cvm-guest-attestation)
sample, which builds the `AttestationClient` the proxies use. The sample is the submodule
`upstream/` (at `4a6b34f`), and our 7 commits on top of it are in `patches/`.

The patches add two options to `AttestationClient`, `-r <runtime-data>` and `-h <host-data>`. Their
values go into the MAA token's `x-ms-runtime.client-payload` as `reportdata` and `hostdata`. The
patches also update upstream's `cvm-guest-attestation.md` for the `snpguest` tool. They are
released under the MIT license.

## Build

Build `AttestationClient` before the proxy images (you need Docker):

```bash
git submodule update --init third_party/cvm-guest-attestation/upstream   # if you cloned without submodules
./third_party/cvm-guest-attestation/build.sh
```

`build.sh` applies the patches (`apply_patches.sh`, safe to re-run), builds `AttestationClient` in
Ubuntu 20.04 (the proxy base image's OS) with `azguestattestation1` 1.0.2, and copies it into the 5
proxy directories.
