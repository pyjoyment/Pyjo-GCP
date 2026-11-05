"""
Pyjo.GCP - Google Cloud for Pyjoyment
=====================================
::

    import Pyjo.GCP.Call
    import Pyjo.GCP.Client

    storage = Pyjo.GCP.Client.new(service='storage')
    print(storage.call(Pyjo.GCP.Call.new('GET', '/storage/v1/b', query={'project': 'myproject'})))

    storage.call_p(Pyjo.GCP.Call.new('GET', '/storage/v1/b/mybucket/o')).then(lambda objects: print(objects)).wait()

:mod:`Pyjo.GCP` is the namespace of the APIs of Google Cloud for
:mod:`Pyjoyment`, which :mod:`Pyjo.UserAgent` calls, without an SDK:
:mod:`Pyjo.GCP.Client` calls the JSON APIs, blocking and non-blocking, with
the calls of :mod:`Pyjo.GCP.Call`, with the access tokens of
:mod:`Pyjo.GCP.Credentials`, which :mod:`Pyjo.GCP.Credentials.Chain` finds as
the Application Default Credentials, and :mod:`Pyjo.GCP.Config` reads the
configuration of gcloud and of the environment.

It is for a program that needs a few calls of Google Cloud and no dependency
for them, not a replacement of the client libraries of Google, which have every
API. What it has is what such a program needs:

* the Application Default Credentials of AIP-4110, in the order of
  google-auth, of :mod:`Pyjo.GCP.Credentials.Chain`: the file of
  ``GOOGLE_APPLICATION_CREDENTIALS``, the one of
  ``gcloud auth application-default login``, and the metadata server of
  Compute Engine, GKE, Cloud Run and Cloud Functions;
* the credentials of each ``type`` of a file of google-auth, which
  :mod:`Pyjo.GCP.Credentials` lists: a user of gcloud, the key of a service
  account, with a self-signed JWT or the domain-wide delegation, an
  impersonated service account, Workload Identity Federation of a file, a
  URL, an executable, AWS or a certificate of X.509, and a user of a
  workforce pool;
* the project and the quota project of the credentials, of the environment
  and of the configuration of gcloud, which :mod:`Pyjo.GCP.Config` reads
  without gcloud;
* the endpoints of a universe domain, of the emulators of
  ``<SERVICE>_EMULATOR_HOST``, and of mTLS with the certificate of a
  workload, with the tokens bound to the certificate of an agent identity of
  :mod:`Pyjo.GCP.X509`;
* the errors of the JSON APIs as :mod:`Pyjo.GCP.Error`, with their status of
  HTTP, their status of ``google.rpc.Status`` and their reason;
* blocking and non-blocking calls alike, of :mod:`Pyjo.Steps`, so that an
  action of Pyjoyment awaits them in its event loop;
* no dependency but Pyjoyment: the RS256 of the keys of the service accounts
  is signed by :mod:`Pyjo.GCP.RSA` in Python, or with the package
  ``cryptography`` of the extra ``cryptography`` when it is installed.

gRPC, the generated clients of the discovery documents, retries,
long-running operations and resumable uploads are left out, until something
needs them.

See also
--------

:mod:`Pyjo.GCP.Client`, :mod:`Pyjo.GCP.Credentials`, :mod:`Pyjo.GCP.Config`,
:mod:`Pyjo.UserAgent`, :mod:`Pyjoyment`, https://github.com/pyjoyment/Pyjoyment.
"""

import importlib.metadata


__version__ = importlib.metadata.version('Pyjo-GCP')
"""The version of the distribution, of its metadata, which the workflow Automated version sets in pyproject.toml."""
