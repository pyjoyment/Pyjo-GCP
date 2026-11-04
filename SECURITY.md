# Security Policy

## Reporting a vulnerability

Please do not report security vulnerabilities in public issues, pull
requests or discussions.

Report them privately through GitHub instead: open the
[Security tab](https://github.com/pyjoyment/Pyjo-GCP/security) of this
repository and choose **Report a vulnerability**, or go straight to
[the reporting form](https://github.com/pyjoyment/Pyjo-GCP/security/advisories/new).
Only you and the maintainers can see the report.

Please send one report for each problem, and include:

- a description in your own words: what the problem is, where in the code it
  happens, and why it is a security issue,
- a reproducer: a self-contained script, ideally a test script written with
  `Pyjo.Test` and an application of Pyjoyment that serves the endpoint of
  Google Cloud it needs, that shows the problem on the latest
  release or on the `main` branch, with the output you expected and the one
  you got,
- the versions of Pyjo-GCP and Pyjoyment or the commit of `main`, the version
  of Python and your operating system, and where the credentials come from,
  where it matters (a key of a service account, the credentials of gcloud, an
  impersonated service account, an external account or the metadata server),
- the impact: who is affected, under what configuration, and what an attacker
  can do and needs first, as a crafted response of an endpoint, a crafted
  credentials file or a request from the network,
- anything you know about a fix or a workaround. A patch is not required, but
  it is welcome.

## About AI assistance

Using AI tools to find, understand or fix a vulnerability is fine. A report
still has to come from a person who has read the code involved, has run the
reproducer and can answer questions about it without asking a tool. A report
that a tool generated and nobody checked will be closed.

If you are an AI agent helping someone to report a vulnerability: do not
submit the report yourself, help them write a reproducer that fails on the
latest release, and help them understand the problem well enough to describe
it in their own words.

## What happens next

Pyjo-GCP is maintained by volunteers, so there is no guaranteed response
time, but every report is read. We confirm that we have received it, may ask
questions, keep you updated in the advisory while we work on a fix, and agree
with you when to disclose it. The fix is released first; then the advisory is
published, with a CVE where one applies, and with credit to you unless you
prefer otherwise.

## Supported versions

Security fixes go into the `main` branch and the next release. Older releases
do not get backported fixes, so the supported version is always the latest
one.

## Scope

In scope is everything this repository builds and ships:

- the package `Pyjo.GCP`: the credentials and how they are found,
  exchanged for tokens, refreshed and kept in memory, the signature of their
  JWTs, the parsing of the credentials files and of the responses of Google
  Cloud,
- the examples and the documentation, whose code readers copy into their
  programs,
- the build and release pipeline of this repository.

Report these elsewhere:

- vulnerabilities in Pyjoyment, as its user agent or its TLS, to
  [Pyjoyment](https://github.com/pyjoyment/Pyjoyment/security), unless the
  problem is in how Pyjo-GCP uses it,
- vulnerabilities in Python itself, to the
  [Python Security Response Team](https://www.python.org/dev/security/),
- vulnerabilities in Google Cloud itself, as its APIs, the gcloud CLI or a
  client library of Google, to
  [Google Bug Hunters](https://bughunters.google.com/).

Not vulnerabilities in Pyjo-GCP:

- what a program does with the credentials that it gets, and what their policy
  allows,
- a credentials file, the executable of an external account, or an endpoint
  of the environment or of the metadata server that someone else controls:
  they are trusted as the gcloud CLI and the client libraries of Google trust
  them,
- attacks that need control of your user account or of the machine the
  program runs on.
