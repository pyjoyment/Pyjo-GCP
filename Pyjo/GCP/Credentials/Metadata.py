"""
Pyjo.GCP.Credentials.Metadata - Credentials of the metadata server
==================================================================
::

    from Pyjo.GCP.Credentials.Metadata import Metadata

    credentials = Metadata().credentials()
    print(credentials.account, credentials.project)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Credentials.Metadata

    provider = Pyjo.GCP.Credentials.Metadata.new(scopes=['https://www.googleapis.com/auth/devstorage.read_only'])
    provider.credentials_p().then(lambda credentials: print(credentials.expiration)).wait()

:mod:`Pyjo.GCP.Credentials.Metadata` is the provider of the credentials of
the service account of the metadata server of Compute Engine, GKE, Cloud Run
and Cloud Functions, of AIP-4115: its token, with the scopes, its email, the
project and the universe domain of the server.

The provider asks the server once whether it is there, as google-auth does:
a request to the IP of the server, ``169.254.169.254``, whose response has
``Metadata-Flavor: Google``, or, without it, on Linux, the product of the
machine, ``Google Compute Engine``, of
``/sys/class/dmi/id/product_name``. Without the server it has no
credentials, as on a machine that is not of Google Cloud, and with
``NO_GCE_CHECK=true`` it does not ask.

The environment variables of google-auth change the server:

* ``GCE_METADATA_HOST``, or ``GCE_METADATA_ROOT``, the host of the requests,
  ``metadata.google.internal`` by default,
* ``GCE_METADATA_IP``, the host of the request that finds the server,
  ``169.254.169.254`` by default,
* ``GCE_METADATA_TIMEOUT``, the timeout of a request, 3 seconds by default,
* ``GCE_METADATA_DETECT_RETRIES``, the attempts of the request that finds the
  server, 3 by default.

See also
--------

:mod:`Pyjo.GCP.Credentials.Provider`, :mod:`Pyjo.GCP.Credentials.Chain`,
https://google.aip.dev/auth/4115,
https://cloud.google.com/compute/docs/metadata/overview.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.File
import Pyjo.Transaction.HTTP
import Pyjo.URL
import Pyjo.UserAgent

from Pyjo.Util import getenv, url_escape

from .. import Credentials
from . import Provider

import os

from collections.abc import Mapping, Sequence
from typing import Any


HOST = 'metadata.google.internal'
"""The host of the metadata server."""

IP = '169.254.169.254'
"""The IP of the metadata server, which finds it."""

PRODUCT_NAME_FILE = '/sys/class/dmi/id/product_name'
"""The file of the product of a machine of Linux, ``Google Compute Engine`` of one of Google Cloud."""

_RETRYABLE = (500, 502, 503, 504)


class Pyjo_GCP_Credentials_Metadata(Provider.object):
    """
    :mod:`Pyjo.GCP.Credentials.Metadata` inherits all attributes and methods
    from :mod:`Pyjo.GCP.Credentials.Provider` and implements the following
    new ones.
    """

    def __init__(
        self,
        *,
        host: str | None = None,
        ip: str | None = None,
        timeout: float | None = None,
        attempts: int | None = None,
        scopes: Sequence[str] | None = None,
        service_account: str = 'default',
        product_name_file: str = PRODUCT_NAME_FILE,
        ua: Pyjo.UserAgent.object | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.Metadata.new()
            provider = Pyjo.GCP.Credentials.Metadata.new(host='127.0.0.1:8080', timeout=1, attempts=1)

        Construct a new :mod:`Pyjo.GCP.Credentials.Metadata` object, with
        the options of :mod:`Pyjo.GCP.Credentials.Provider`, and those of the
        environment by default.
        """
        self.timeout = timeout if timeout is not None else _number('GCE_METADATA_TIMEOUT', 3)
        """::

            seconds = provider.timeout

        The timeout of a request, of the ``GCE_METADATA_TIMEOUT`` environment
        variable, or 3 seconds, of a new :attr:`ua` of the provider, which
        keeps no connections, as a token comes once an hour.
        """

        super().__init__(
            ua=ua
            or Pyjo.UserAgent.new(connect_timeout=self.timeout, inactivity_timeout=self.timeout, max_connections=0),
            **kwargs,
        )

        self.host = host or getenv('GCE_METADATA_HOST') or getenv('GCE_METADATA_ROOT') or HOST
        """::

            host = provider.host

        The host of the requests, of the ``GCE_METADATA_HOST`` or
        ``GCE_METADATA_ROOT`` environment variable, or
        ``metadata.google.internal``, with a port too.
        """

        self.ip = ip or getenv('GCE_METADATA_IP') or IP
        """::

            ip = provider.ip

        The host of the request that finds the server, of the
        ``GCE_METADATA_IP`` environment variable, or ``169.254.169.254``.
        """

        self.attempts = attempts if attempts is not None else int(_number('GCE_METADATA_DETECT_RETRIES', 3))
        """::

            attempts = provider.attempts

        The number of the attempts of the request that finds the server, of
        the ``GCE_METADATA_DETECT_RETRIES`` environment variable, or 3, and
        of a request that fails with a status of 5xx or without a
        connection, at least 1.
        """

        self.disabled = (getenv('NO_GCE_CHECK') or '').strip().lower() == 'true'
        """::

            boolean = provider.disabled

        Whether the provider does not ask for the server, of the
        ``NO_GCE_CHECK`` environment variable ``true``.
        """

        self.scopes = list(scopes) if scopes else []
        """::

            scopes = provider.scopes

        The scopes of the token, or none for the scopes of the service
        account of the machine.
        """

        self.service_account = service_account
        """::

            name = provider.service_account

        The service account of the machine, ``default`` by default, or its
        email.
        """

        self.product_name_file = product_name_file
        """::

            path = provider.product_name_file

        The file of the product of the machine on Linux,
        ``/sys/class/dmi/id/product_name``.
        """

        self.detected: bool | None = None
        """::

            boolean = provider.detected

        Whether the server is there, once the provider has asked, or
        ``None``.
        """

        self._details: dict[str, str | None] | None = None

    async def detect(self) -> bool:
        """::

            boolean = await provider.detect()

        Whether the server is there, of the response to the request to
        :attr:`ip` with ``Metadata-Flavor: Google``, or of the product of
        the machine on Linux.
        """
        for _ in range(max(self.attempts, 1)):
            try:
                tx = await self.start(self.ua.build_tx('GET', f'http://{self.ip}', {'Metadata-Flavor': 'Google'}))
            except Pyjo.Exception.object:
                continue
            if tx.res.code == 200 and tx.res.headers.header('Metadata-Flavor') == 'Google':
                return True
            if tx.res.code not in _RETRYABLE:
                break
        if os.name == 'nt':
            return False
        product = Pyjo.File.path(self.product_name_file)
        return product.is_file and (product.slurp('UTF-8') or '').strip().startswith('Google')

    async def fetch(self) -> Credentials.object | None:
        """::

            credentials = await provider.fetch()

        The token of the service account of the server, with its email, the
        project and the universe domain of the server, or ``None`` without
        the server.
        """
        if self.disabled:
            return None
        if self.detected is None:
            self.detected = await self.detect()
        if not self.detected:
            return None
        account = url_escape(self.service_account, r'^A-Za-z0-9\-._~@')
        query = {'scopes': ','.join(self.scopes)} if self.scopes else None
        tx = await self.get(f'instance/service-accounts/{account}/token', query)
        data = Provider.parse_token(tx, 'the metadata server of Google Cloud')
        if self._details is None:
            self._details = {
                'account': await self.text(f'instance/service-accounts/{account}/email'),
                'project': await self.text('project/project-id'),
                'universe_domain': await self.text('universe/universe-domain'),
            }
        return Credentials.new(
            token=data['access_token'],
            expiration=Credentials.expiration_in(data['expires_in']) if 'expires_in' in data else None,
            project=self._details['project'],
            universe_domain=self._details['universe_domain'] or 'googleapis.com',
            account=self._details['account'],
            provider='metadata',
        )

    async def get(self, path: str, query: Mapping[str, str] | None = None) -> Pyjo.Transaction.HTTP.object:
        """::

            tx = await provider.get('project/project-id')

        The transaction of a request of a path of ``/computeMetadata/v1/`` of
        :attr:`host`, with ``Metadata-Flavor: Google``, tried again for a
        status of 5xx or without a connection, or a :mod:`Pyjo.Exception`
        of the last connection that fails.
        """
        url = Pyjo.URL.new(f'http://{self.host}/computeMetadata/v1/{path}')
        if query:
            url.query.append(dict(query))
        error: Exception | None = None
        tx: Pyjo.Transaction.HTTP.object | None = None
        for _ in range(max(self.attempts, 1)):
            try:
                tx = await self.start(self.ua.build_tx('GET', url.clone(), {'Metadata-Flavor': 'Google'}))
            except Pyjo.Exception.object as e:
                error = e
                continue
            if tx.res.code not in _RETRYABLE:
                return tx
        if tx is not None:
            return tx
        raise Pyjo.Exception.new(f'Cannot reach the metadata server of Google Cloud: {error}')

    async def text(self, path: str) -> str | None:
        """::

            project = await provider.text('project/project-id')

        The text of a path of the server, or ``None`` of one that is not
        there, or a :mod:`Pyjo.Exception` of another status.
        """
        tx = await self.get(path)
        if tx.res.code == 404:
            return None
        if tx.res.code != 200:
            raise Pyjo.Exception.new(
                f'Cannot get {path} of the metadata server of Google Cloud: {tx.res.code} {tx.res.message or ""}'.strip()
            )
        return tx.res.text.strip() or None


def _number(name: str, default: float) -> float:
    try:
        return float(getenv(name) or default)
    except ValueError:
        return default


new = Pyjo_GCP_Credentials_Metadata.new
object = Pyjo_GCP_Credentials_Metadata
Metadata = Pyjo_GCP_Credentials_Metadata
