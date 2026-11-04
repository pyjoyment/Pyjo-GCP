[![Home](https://img.shields.io/badge/%F0%9F%8F%A0-Pyjoyment-02a7a0)](https://github.com/pyjoyment/Pyjoyment)
[![GitHub](https://img.shields.io/github/stars/pyjoyment/Pyjo-GCP?style=flat&label=GitHub%20%E2%AD%90&logo=github)](https://github.com/pyjoyment/Pyjo-GCP)
[![Documentation](https://img.shields.io/badge/docs-Read_the_Docs-blue?logo=readthedocs&logoColor=white)](https://pyjoyment.readthedocs.io/projects/pyjo-gcp/en/stable/)
[![License](https://img.shields.io/github/license/pyjoyment/Pyjo-GCP.svg)](https://github.com/pyjoyment/Pyjo-GCP/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/Pyjo-GCP?logo=pypi&logoColor=white)](https://pypi.org/project/Pyjo-GCP/)
[![Tests](https://github.com/pyjoyment/Pyjo-GCP/actions/workflows/tests.yaml/badge.svg?branch=main)](https://github.com/pyjoyment/Pyjo-GCP/actions/workflows/tests.yaml)

# Pyjo-GCP

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/pyjoyment/Pyjoyment/main/Pyjoyment/resources/public/pyjo/logo-white-4x.png">
    <img src="https://raw.githubusercontent.com/pyjoyment/Pyjoyment/main/Pyjoyment/resources/public/pyjo/logo-black-4x.png" alt="Pyjoyment" width="322">
  </picture>
</p>

Google Cloud for [Pyjoyment](https://github.com/pyjoyment/Pyjoyment): the
requests of its user agent to the APIs of Google Cloud, with the Application
Default Credentials that the client libraries of Google find, without an SDK.
It is for a program that needs a few calls of Google Cloud and no dependency
for them, not a replacement of the client libraries of Google, which have every
API.

The distribution is at its beginning: the plan is in the
[issues](https://github.com/pyjoyment/Pyjo-GCP/issues) of this repository.

## Installation

From [PyPI](https://pypi.org/project/Pyjo-GCP/), with
[Pyjoyment](https://pypi.org/project/Pyjoyment/), which it depends on:

```sh
pip install Pyjo-GCP
```

or, in a project managed with [uv](https://docs.astral.sh/uv/):

```sh
uv add Pyjo-GCP
```

The development version is installed from the Git repository:

```sh
pip install git+https://github.com/pyjoyment/Pyjo-GCP
```

## Documentation

The documentation of the API is on
[Read the Docs](https://pyjoyment.readthedocs.io/projects/pyjo-gcp/en/stable/).

## License

Artistic License 2.0, as Pyjoyment.
