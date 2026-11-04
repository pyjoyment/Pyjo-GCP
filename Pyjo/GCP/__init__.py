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
API.

See also
--------

:mod:`Pyjo.GCP.Client`, :mod:`Pyjo.GCP.Credentials`, :mod:`Pyjo.GCP.Config`,
:mod:`Pyjo.UserAgent`, :mod:`Pyjoyment`, https://github.com/pyjoyment/Pyjoyment.
"""

import importlib.metadata


__version__ = importlib.metadata.version('Pyjo-GCP')
"""The version of the distribution, of its metadata, which the workflow Automated version sets in pyproject.toml."""
