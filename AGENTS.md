# Agent Guide: Pyjo-GCP

## Overview

`Pyjo.GCP` calls the APIs of Google Cloud with `Pyjo.UserAgent` of
Pyjoyment, without an SDK, in a distribution of its own, as Pyjoyment has no
business with one cloud. It is for a program that needs a few calls of Google
Cloud and no dependency for them, not a replacement of the client libraries of
Google: what it has is what such a program needs, the credentials that the
client libraries find, the tokens of OAuth 2.0 that they exchange them for,
and a client of the JSON APIs, not the generated clients of every API. The
conventions are those of Pyjoyment: read its `AGENTS.md` in the checkout next
to this one, `../Pyjoyment/AGENTS.md`. The plan is in the issues of this
repository.

Pyjo-GCP is the counterpart of Pyjo-AWS, in the checkout next to this one,
`../Pyjo-AWS`, which is made the same way and is the model of its design: read
its `AGENTS.md` before a module of this one is written.

## The Reference

The reference is the behaviour of the client libraries of Google, as the AIPs
of authentication describe it, https://google.aip.dev/auth, so that a program
finds the credentials and the project that the gcloud CLI and the client
libraries find:

- AIP-4110, Application Default Credentials: the order of the credentials, of
  `GOOGLE_APPLICATION_CREDENTIALS`, of the file of
  `gcloud auth application-default login`, and of the metadata server,
- AIP-4111, Self-signed JWT, and AIP-4112, Service Account Keys: the keys of a
  service account, with a JWT of RS256 signed by the program itself or
  exchanged for a token,
- AIP-4113, gcloud CLI Integration: the configuration directory of gcloud,
  `CLOUDSDK_CONFIG`, and its file of the credentials,
- AIP-4115, Default Credentials For Google Cloud Virtual Environments: the
  metadata server of Compute Engine, GKE, Cloud Run and Cloud Functions,
- AIP-4117, External Account Credentials: Workload Identity Federation, the
  token of another identity provider exchanged with the STS of Google.

Where an AIP is silent, the reference is `google-auth` of Python,
https://github.com/googleapis/google-auth-library-python, as botocore is the
one of Pyjo-AWS: `google/auth/_default.py` for the order and the project,
`google/oauth2` and `google/auth` for each kind of credentials.

## The Model of Pyjo-AWS

The mechanisms of Pyjo-AWS are meant to be taken as they are, and changed only
where Google Cloud differs:

- `Pyjo.AWS.Steps`, the coroutine of the operations that `run` drives
  blocking and `run_p` non-blocking, so that a provider of credentials and a
  call of the client are written once for both modes,
- `Pyjo.AWS.Credentials.Provider` and `Pyjo.AWS.Credentials.Chain`: `fetch`
  as a coroutine of the steps, `None` of a provider that is not configured, an
  exception of one that is configured and fails, which ends the chain, and the
  credentials kept until `refresh` seconds before their expiration, which a
  burst of calls gets once,
- `Pyjo.AWS.Client`: the credentials resolved before the transaction starts,
  and the errors of the API as exceptions with their code, message and status,
- `Pyjo.AWS.ECDSA`: the package `cryptography` of an extra when it is
  installed, and Python otherwise, which is how the RS256 of the keys of a
  service account is meant to be signed, so that the distribution depends on
  nothing but Pyjoyment,
- the tests that serve the endpoints of the cloud with an application of
  Pyjoyment.Lite, in a process of its own where a provider has a user agent of
  its own, as `t/AWS_Credentials_Metadata.py`.

What differs is the authorization: Google Cloud takes a bearer token of OAuth
2.0 in `Authorization`, not a signature of each request, so the credentials of
Pyjo-GCP are a token with its expiration, and the client adds the header in
the event `start` of its user agent. The JSON APIs of Google share one
protocol, with the error of `google.rpc.Status`, so the client needs no class
of a protocol of each kind of API, as Pyjo-AWS does.

Pyjo-GCP does not depend on Pyjo-AWS: a module that both need, as the steps,
is copied, until it has a distribution of its own or a place in Pyjoyment.

## Imports of the Package

The modules of the distribution import the package and each other relatively,
`from .. import GCP` and `from . import Steps`, not as `import Pyjo.GCP.Steps`:
pyright takes `Pyjo` for the regular package of Pyjoyment in `.venv`, which
hides the namespace that `extend_path` keeps open, so it does not find
`Pyjo.GCP` of the checkout. The tests and the documentation import them as
`Pyjo.GCP.Steps`, which Python finds through `extend_path`.

The package and the tests take what Pyjoyment has, as the distribution depends
on it already: the hashes and Base64 of `Pyjo.Util`, as `sha256_sum` and
`b64url_encode`, the JSON of `Pyjo.JSON`, and the times of RFC 3339 of
`Pyjo.Date`, not `hashlib`, `base64` and the formats of `datetime`.

## Security

The files of secrets of Pyjoyment are git-ignored in `.gitignore` and denied to
Claude Code in `.claude/settings.json`, and so are the credentials of gcloud on
the machine, `application_default_credentials.json`, `credentials.db`,
`access_tokens.db` and `legacy_credentials` of `~/.config/gcloud`. A key of a
service account has no name of its own, so a file of one that is not in the
repository is not denied by a rule, and is never read. A test never reads the
files of the machine: it sets `GOOGLE_APPLICATION_CREDENTIALS`,
`CLOUDSDK_CONFIG` and `HOME` to files of its own, with a key made for the
test, and serves the endpoints of Google that it needs with an application of
Pyjoyment, with `NO_GCE_CHECK` or `GCE_METADATA_HOST` of its own, so that no
test asks the metadata server of the machine.

## Development

The distribution depends on the release of Pyjoyment on PyPI, with the lowest
version that has what it uses, which `uv.lock` pins. A change of Pyjoyment that
is not released yet would be its Git repository in `[tool.uv.sources]` of
`pyproject.toml`, until its release, and not a path to the checkout next to
this one: uv applies the sources of a dependency of Git, so whoever installs
the distribution from Git would get a subdirectory of this repository that
does not exist. The tests lay the checkout next to this one over it with
`--with-editable`, so that they test what is there:

```sh
mise exec -- uv sync
mise exec -- uv run --with-editable ../Pyjoyment python -m Pyjo.Prove -l -r t
```

Perl's `prove` runs them too, with `.proverc`, under `uv run`, whose `python`
is the one of the environment, where Pyjoyment and the distribution are
installed, so that it needs no `PYTHONPATH`, unlike in Pyjoyment:

```sh
mise exec -- uv run --with-editable ../Pyjoyment prove -r t
```

The package is in the namespace `Pyjo` of Pyjoyment, which `extend_path` keeps
open, but it changes nothing of Pyjoyment, so the suite of Pyjoyment is not
run with it installed, unlike the one of a distribution of a reactor, which
runs on the reactor. What the distribution could break is the namespace, with
an `__init__.py` of `Pyjo` of its own, which the workflow Build checks.

The workflow Tests runs the tests of the distribution against the release of
`uv.lock`, without `--with-editable`, so that a pull request tests what an
installation gets. A dispatch with `pyjoyment-ref` lays a checkout of the ref
over it, as in development, so that what the next release of Pyjoyment breaks
is known before the release.

Trunk checks the files with the linters of Pyjoyment, from `.trunk/trunk.yaml`:

```sh
trunk check --all
```

actionlint is the one of the maintained fork kjanat/actionlint, whose releases
continue those of rhysd/actionlint after 1.7.12, as in Pyjoyment: `downloads`
in `.trunk/trunk.yaml` replaces the URLs of the plugin with those of the fork,
whose files have the same names.

Biome formats and lints JSON, Markdown and YAML, with `biome.jsonc`, in the
place of prettier, markdownlint and yamlfmt, as in Pyjoyment, and yamllint
checks what Biome does not, as the duplicated keys. The version of Biome is
the pinned one of `.trunk/trunk.yaml`, where `!` keeps it from
`trunk upgrade`, and which Renovate bumps, as in the repositories of
freelensapp: the repository has no `package.json` of its own. Renovate cannot
run `biome migrate`, so the workflow Biome Migrate runs it with
`npx --yes @biomejs/biome@<version>` of that version, migrates `biome.jsonc` on
the branch of Renovate and commits it with the token of the workflow, as the
author that `gitIgnoredAuthors` of `.renovaterc.json` names, so that Renovate
keeps updating the branch, and starts the checks of the commit with
`workflow_dispatch`; anywhere else, a `biome.jsonc` that this Biome would
migrate fails the check. The definition of Biome in `.trunk/trunk.yaml` is
the one of Pyjoyment, which explains why it is not the one of the plugin of
Trunk.

Its pyright needs the environment of `uv sync`, `.venv`, which `tool.pyright` of
`pyproject.toml` names, as the package imports Pyjoyment; Trunk Check of CI
runs `uv sync` first. The tests and `docs/conf.py` are not checked by pyright:
for them it takes the regular package `Pyjo` of Pyjoyment, which hides
`Pyjo.GCP` of the checkout.

The wheel has only the package `Pyjo.GCP` (`only-include` of hatchling), not
the `__init__.py` of `Pyjo`, which is the one of Pyjoyment; the workflow Build
checks it.

The documentation is on Read the Docs, a subproject of the one of Pyjoyment:
the docstrings of the package, which autodoc imports, as in Pyjoyment. Read the
Docs installs it with `uv sync` of `uv.lock` and the group `docs`, not with pip
and a `docs/requirements.txt` as Pyjoyment does, so that it builds with the
versions of the lock, as the workflow Docs does. The links to the
modules of Pyjoyment come from intersphinx. The workflow Docs builds it with
`-W`, as Read the Docs does, with the Pyjoyment of `uv.lock`:

```sh
mise exec -- uv run --group docs --with-editable ../Pyjoyment sphinx-build -W --keep-going -b html docs docs/_build/html
```

The workflow Tests ends with the job `Tests`, the one check of it that the
ruleset of `main` requires, as in Pyjoyment: it fails when a job of the
matrix failed or was cancelled, so a new version of Python needs no change of
the ruleset.

## Releases

The releases are those of Pyjoyment, with its workflows: a release is a tag of
the version of `pyproject.toml`, without a `v`, as `0.1.0`, which Automated
version sets with `uv version`, the components of its `--bump` from a list, as
`patch dev` or `minor rc`, or the version of `manual`, in the pull request of
the branch `automated/version`. After a release, a pre-release goes with the
release that it comes before, as PEP 440 orders `0.2.0.dev1` before `0.2.0`,
so `dev` alone after `0.2.0` fails. Automated tag tags the merge commit of that pull
request when it is merged, or with a comment `/tag` of a maintainer on it, and
starts Release on the tag. A development version, as `0.1.1.dev1`, is not
tagged. The version is static in `pyproject.toml`, as `uv version` cannot set a
dynamic one, and `__version__` of the package reads it from the metadata of
the distribution.

Release builds the sdist and the wheel, attests their build provenance with
`actions/attest`, and makes a draft of the GitHub release with them, whose
notes are rewritten before it is published, and an SBOM in SPDX, attested
with them. The package bundles nothing, unlike the one of Pyjoyment, whose SBOM
lists the JavaScript libraries of its package, so the SBOM is what an
installation of the wheel gets: the distribution and its dependencies at the
versions of `uv.lock`, installed in a virtual environment of their own, which
Syft scans. Syft on `uv.lock` itself would take its dependency groups too, as
Sphinx, which an installation does not get. The sdist does not
carry the SBOM, as the one of Pyjoyment does, as it is made of the wheel,
which is built after the sdist.

The workflow PyPI, run manually, publishes the files of the latest published
release, or of the release of the tag of its input, on PyPI once their
attestations of Release verify, in the environment `publishing`, which waits
for an approval and takes `main` and tags only. The trusted publisher of PyPI
names `pypi.yaml` and that environment.

```sh
gh attestation verify pyjo_gcp-0.1.0.tar.gz -R pyjoyment/Pyjo-GCP
```
