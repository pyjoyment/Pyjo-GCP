"""
Pyjo.GCP.Credentials - Credentials of Google Cloud
==================================================
::

    from Pyjo.GCP.Credentials import Credentials

    credentials = Credentials(token='ya29.a0AfH6SM...')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Credentials.Chain

    # The Application Default Credentials, blocking
    credentials = Pyjo.GCP.Credentials.Chain.new().credentials()
    print(credentials.project, credentials.expiration, credentials.provider)

    # Non-blocking
    Pyjo.GCP.Credentials.Chain.new().credentials_p().then(lambda credentials: print(credentials.provider)).wait()

:mod:`Pyjo.GCP.Credentials` is the credentials of Google Cloud that
authorize a request: an access token of OAuth 2.0, which a request has as
``Authorization: Bearer``, with its expiration, and what the credentials
know of the project, the quota project and the universe domain. A provider
of :mod:`Pyjo.GCP.Credentials.Provider` gets them, as
:mod:`Pyjo.GCP.Credentials.Chain` gets the Application Default Credentials.

The providers are those of the credentials of google-auth, of a file of
credentials of its ``type``, which :mod:`Pyjo.GCP.Credentials.File` makes
the provider of, and of the metadata server:

.. list-table::
    :header-rows: 1

    * - Credentials
      - ``type`` of the file
      - Provider
    * - a user of ``gcloud auth application-default login``
      - ``authorized_user``
      - :mod:`Pyjo.GCP.Credentials.AuthorizedUser`
    * - the key of a service account, with a self-signed JWT or the
        domain-wide delegation
      - ``service_account``
      - :mod:`Pyjo.GCP.Credentials.ServiceAccount`
    * - an impersonated service account, of the credentials of its source
      - ``impersonated_service_account``
      - :mod:`Pyjo.GCP.Credentials.Impersonated`
    * - Workload Identity Federation of a token of a file or a URL, or of a
        certificate of X.509
      - ``external_account``
      - :mod:`Pyjo.GCP.Credentials.IdentityPool`
    * - Workload Identity Federation of a token of an executable
      - ``external_account`` with ``executable``
      - :mod:`Pyjo.GCP.Credentials.Pluggable`
    * - Workload Identity Federation of AWS
      - ``external_account`` of AWS
      - :mod:`Pyjo.GCP.Credentials.AWS`
    * - a user of a workforce pool, of
        ``gcloud auth application-default login --login-config``
      - ``external_account_authorized_user``
      - :mod:`Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser`
    * - the service account of Compute Engine, GKE, Cloud Run and Cloud
        Functions
      - none, the metadata server
      - :mod:`Pyjo.GCP.Credentials.Metadata`

See also
--------

:mod:`Pyjo.GCP.Credentials.Provider`, :mod:`Pyjo.GCP.Credentials.Chain`,
:mod:`Pyjo.GCP`.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Date
import Pyjo.Exception

import datetime

from typing import Any


CLOUD_PLATFORM = 'https://www.googleapis.com/auth/cloud-platform'
"""The scope of all the APIs of Google Cloud, of the tokens of the providers that take scopes by default."""


class Pyjo_GCP_Credentials(Pyjo.Base.object):
    """
    :mod:`Pyjo.GCP.Credentials` inherits all attributes and methods from
    :mod:`Pyjo.Base` and implements the following new ones.
    """

    def __init__(
        self,
        *,
        token: str,
        expiration: datetime.datetime | None = None,
        project: str | None = None,
        quota_project: str | None = None,
        universe_domain: str | None = None,
        account: str | None = None,
        provider: str | None = None,
    ) -> None:
        """::

            credentials = Pyjo.GCP.Credentials.new(token='ya29.a0AfH6SM...')

        Construct a new :mod:`Pyjo.GCP.Credentials` object.
        """
        self.token = token
        """::

            token = credentials.token

        The access token.
        """

        self.expiration = expiration
        """::

            expiration = credentials.expiration

        The time when the token expires, with its time zone, or ``None`` for
        a token whose expiration is not known.
        """

        self.project = project
        """::

            project = credentials.project

        The project of the credentials, as the one of the key of a service
        account, or of the environment of :mod:`Pyjo.GCP.Credentials.Chain`,
        or ``None``.
        """

        self.quota_project = quota_project
        """::

            project = credentials.quota_project

        The project that the quota and the billing of the requests go to, of
        the header ``x-goog-user-project``, or ``None``.
        """

        self.universe_domain = universe_domain
        """::

            domain = credentials.universe_domain

        The universe domain of the credentials, or ``None`` for the one of
        :mod:`Pyjo.GCP.Config`.
        """

        self.account = account
        """::

            account = credentials.account

        The account of the credentials, as the email of a user or of a service
        account, where the provider knows it, or ``None``.
        """

        self.provider = provider
        """::

            name = credentials.provider

        The name of the provider of the credentials, as ``authorized_user``,
        or ``None``.
        """

    def __repr__(self) -> str:
        # Without the token, which a log or a traceback would show
        return f'<Credentials account={self.account!r} provider={self.provider!r}>'

    def copy(self, **changes: Any) -> 'Pyjo_GCP_Credentials':
        """::

            credentials = credentials.copy(project='myproject')

        A new :mod:`Pyjo.GCP.Credentials` object of the same attributes,
        with the changes of the arguments.
        """
        return Pyjo_GCP_Credentials(**{**vars(self), **changes})

    def expires_in(self, now: datetime.datetime | None = None) -> float | None:
        """::

            seconds = credentials.expires_in()

        The number of seconds until the token expires, negative once it has,
        or ``None`` for a token whose expiration is not known.
        """
        if self.expiration is None:
            return None
        return (self.expiration - (now or datetime.datetime.now(datetime.UTC))).total_seconds()


def expiration_in(seconds: Any) -> datetime.datetime:
    """::

        expiration = Pyjo.GCP.Credentials.expiration_in(3599)

    The time of the expiration of a token of ``expires_in`` of OAuth 2.0, a
    number of seconds from now, or a string of it, as some endpoints give it.
    """
    try:
        return datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=int(seconds))
    except (TypeError, ValueError) as e:
        raise Pyjo.Exception.new(f'Invalid expiration of a token of Google Cloud: {seconds!r}') from e


def parse_time(value: str) -> datetime.datetime:
    """::

        expiration = Pyjo.GCP.Credentials.parse_time('2026-11-04T12:00:00Z')

    A time of RFC 3339, as the expiration of a token of IAM Credentials, with
    its time zone, UTC when it has none.
    """
    date = Pyjo.Date.new(value.strip())
    if date.epoch is None:
        raise Pyjo.Exception.new(f'Invalid expiration of a token of Google Cloud: {value!r}')
    return date.to_datetime()


new = Pyjo_GCP_Credentials.new
object = Pyjo_GCP_Credentials
Credentials = Pyjo_GCP_Credentials
