# ExclaveFL

ExclaveFL is a federated learning system that provides verifiable claims about how a model was
trained, using runtime attestation from exclaves. This repository contains its implementation on
NVIDIA FLARE and Azure confidential VMs. Paper:
[ExclaveFL: Verifiable Claims for Federated Learning using Exclaves](https://lsds.doc.ic.ac.uk/sites/default/files/socc26.pdf)
(SoCC '26).

> **Research prototype.** It is released to support research and is provided as is; use it at your
> own risk.

## What's in the repo

- `azure/`: the exclave implementation (training, differential privacy, aggregation and model
  update), the attested proxies, the attestation and data-disk setup, the microbenchmarks, and the
  scripts that build the VM images and run the experiments on Azure.
- `nvflare-ext/`: the `confidential_fl` package for NVFlare and the 12 evaluation jobs.
- `third_party/`: NVFlare, Azure's guest-attestation sample and Azure's H100 onboarding scripts
  (`conf-gpu`) as submodules, and our patches to the guest-attestation sample.

The attested proxy is implemented in C++ as Envoy with an attested-TLS extension. The proxy itself
remains closed-source; it is provided as the Docker image
[`guojinnan/confidential-envoy-base`](https://hub.docker.com/r/guojinnan/confidential-envoy-base),
on which the proxy images in this repo are built.

## Getting started

```bash
git clone --recurse-submodules https://github.com/microsoft/exclave-fl
```

Then follow [azure/README.md](azure/README.md) to build the images and run an experiment. To install
the Python package on your own machine, see [nvflare-ext/README.md](nvflare-ext/README.md).

## Acknowledgements

ExclaveFL relies on open-source third-party components, including
[NVIDIA FLARE](https://github.com/NVIDIA/NVFlare),
[microsoft/confidential-ai](https://github.com/microsoft/confidential-ai) and Azure's
[confidential-computing-cvm-guest-attestation](https://github.com/Azure/confidential-computing-cvm-guest-attestation).
They are attributed in [NOTICE](NOTICE).

## Citation

If you use ExclaveFL in your research, please cite our paper:

```bibtex
@inproceedings{exclavefl,
  author    = {Guo, Jinnan and Vaswani, Kapil and Paverd, Andrew and Pietzuch, Peter},
  title     = {ExclaveFL: Verifiable Claims for Federated Learning using Exclaves},
  booktitle = {Proceedings of the 2026 ACM Symposium on Cloud Computing Volume 1},
  series    = {SoCC '26},
  pages     = {103--116},
  year      = {2026},
  publisher = {Association for Computing Machinery},
  doi       = {10.1145/3815789.3827953}
}
```

## License

This project is licensed under the MIT license ([LICENSE](LICENSE)). Parts of the code are based on
NVIDIA FLARE and Hugging Face transformers (Apache-2.0); [NOTICE](NOTICE) lists them and the
submodules with their licenses.

## Security

See [SECURITY.md](SECURITY.md) for how to report security vulnerabilities.

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
