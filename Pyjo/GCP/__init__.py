"""
Pyjo.GCP - Google Cloud for Pyjoyment
=====================================
::

    import Pyjo.GCP

    print(Pyjo.GCP.__version__)

:mod:`Pyjo.GCP` is the namespace of the APIs of Google Cloud for
:mod:`Pyjoyment`, which :mod:`Pyjo.UserAgent` calls, without an SDK, with the
credentials that the client libraries of Google find, the Application Default
Credentials.

It is for a program that needs a few calls of Google Cloud and no dependency
for them, not a replacement of the client libraries of Google, which have every
API.

See also
--------

:mod:`Pyjo.UserAgent`, :mod:`Pyjoyment`, https://github.com/pyjoyment/Pyjoyment.
"""

import importlib.metadata


__version__ = importlib.metadata.version('Pyjo-GCP')
"""The version of the distribution, of its metadata, which the workflow Automated version sets in pyproject.toml."""
