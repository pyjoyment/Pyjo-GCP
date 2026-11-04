"""
Pyjo.GCP.Credentials.Provider - Base class of the providers of credentials
==========================================================================
::

    from Pyjo.GCP.Credentials import Credentials
    from Pyjo.GCP.Credentials.Provider import Provider

    class Static(Provider):
        async def fetch(self):
            return Credentials(token='ya29.static')

    credentials = Static().credentials()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Credentials
    import Pyjo.GCP.Credentials.Provider

    class Service(Pyjo.GCP.Credentials.Provider.object):
        async def fetch(self):
            tx = await self.start(self.ua.build_tx('GET', 'http://127.0.0.1:8080/token'))
            data = Pyjo.GCP.Credentials.Provider.parse_token(tx, 'the service')
            return Pyjo.GCP.Credentials.new(
                token=data['access_token'], expiration=Pyjo.GCP.Credentials.expiration_in(data['expires_in'])
            )

    Service.new().credentials_p().then(lambda credentials: print(credentials.expiration)).wait()

:mod:`Pyjo.GCP.Credentials.Provider` is the base class of the providers of
:mod:`Pyjo.GCP.Credentials`. A provider gets its credentials in
:meth:`~Pyjo_GCP_Credentials_Provider.fetch`, keeps them until they are about
to expire, and gets them again then.

:meth:`~Pyjo_GCP_Credentials_Provider.fetch` is a coroutine, which awaits
what it needs to wait for, so that the same code runs blocking, in
:meth:`~Pyjo_GCP_Credentials_Provider.credentials`, and non-blocking, in
:meth:`~Pyjo_GCP_Credentials_Provider.credentials_p`:

* a transaction of :meth:`~Pyjo_GCP_Credentials_Provider.start`, which
  :attr:`~Pyjo_GCP_Credentials_Provider.ua` starts, gives the transaction
  back with its response, or raises the :mod:`Pyjo.Exception` of an error of
  the connection;
* a program of :meth:`~Pyjo_GCP_Credentials_Provider.run` gives its exit
  code, its output and its error, or raises the :mod:`Pyjo.Exception` of a
  program that cannot be run;
* the :meth:`~Pyjo_GCP_Credentials_Provider.steps` of another provider give
  its credentials.

:mod:`Pyjo.GCP.Steps` runs the coroutine, without an event loop, so it
awaits nothing else, not a :mod:`Pyjo.Promise` and not a future of asyncio,
which is a :exc:`TypeError`. :meth:`~Pyjo_GCP_Credentials_Provider.fetch` may
be a generator too, which yields the transactions and the programs, and takes the
credentials of another provider with ``yield from`` of its
:meth:`~Pyjo_GCP_Credentials_Provider.steps`: ::

    class Service(Provider):
        def fetch(self):
            tx = yield self.start(self.ua.build_tx('GET', 'http://127.0.0.1:8080/token'))
            ...

What the coroutine returns is the credentials, or ``None`` when the
provider is not configured, as a file of credentials that does not exist, so that
:mod:`Pyjo.GCP.Credentials.Chain` asks the next one. An exception is an error
of a provider that is configured, which ends the chain.

See also
--------

:mod:`Pyjo.GCP.Credentials`, :mod:`Pyjo.GCP.Credentials.Chain`, :mod:`Pyjo.GCP.Steps`.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.Promise
import Pyjo.Transaction.HTTP
import Pyjo.UserAgent

from .. import Credentials, Steps

from collections.abc import Sequence
from typing import Any, cast


class Pyjo_GCP_Credentials_Provider(Pyjo.Base.object):
    """
    :mod:`Pyjo.GCP.Credentials.Provider` inherits all attributes and methods
    from :mod:`Pyjo.Base` and implements the following new ones.
    """

    def __init__(self, *, ua: Pyjo.UserAgent.object | None = None, refresh: float = 225) -> None:
        """::

            provider = Provider.new()
            provider = Provider.new(ua=Pyjo.UserAgent.new(request_timeout=5), refresh=600)

        Construct a new provider.
        """
        self.ua = ua or Pyjo.UserAgent.new()
        """::

            ua = provider.ua
            provider.ua = Pyjo.UserAgent.new()

        The user agent of the requests of the provider, a new
        :mod:`Pyjo.UserAgent` object by default.
        """

        self.refresh = refresh
        """::

            seconds = provider.refresh
            provider.refresh = 600

        The number of seconds before their expiration when the credentials are
        got again, 225 by default, 3 minutes and 45 seconds, as google-auth has
        it.
        """

        self.cached: Credentials.object | None = None
        """::

            credentials = provider.cached
            provider.cached = None

        The credentials that the provider got last, which it gives until they
        are about to expire, or ``None``, which makes it get them again.
        """

        self._pending: Pyjo.Promise.object | None = None

    def credentials(self) -> Credentials.object | None:
        """::

            credentials = provider.credentials()

        The credentials, :attr:`cached` ones or new ones, blocking, or
        ``None`` when the provider is not configured.
        """
        return self.steps().run(self.ua)

    def credentials_p(self) -> Pyjo.Promise.object:
        """::

            promise = provider.credentials_p()

        Same as :meth:`credentials`, but non-blocking, and returns a
        :mod:`Pyjo.Promise` object. The calls while the provider gets the
        credentials get the same promise, so that it gets them once.
        """
        if self.is_fresh():
            return Pyjo.Promise.resolve(self.cached)
        if self._pending is None:
            pending = self.steps().run_p(self.ua)

            def done(*_: Any) -> None:
                self._pending = None

            pending.then(done, done)
            self._pending = pending
        return self._pending

    async def fetch(self) -> Credentials.object | None:
        """::

            credentials = await provider.fetch()

        Get new credentials, a coroutine that awaits what it waits for, as the
        description of the class says, and returns the credentials or ``None``.
        A subclass implements it; this one has no credentials.
        """
        return None

    def is_fresh(self) -> bool:
        """::

            boolean = provider.is_fresh()

        Whether the provider has :attr:`cached` credentials that are not about
        to expire.
        """
        if self.cached is None:
            return False
        expires_in = self.cached.expires_in()
        return expires_in is None or expires_in > self.refresh

    def run(self, args: Sequence[str], input: bytes = b'') -> Steps.Command:
        """::

            code, out, err = await provider.run(['gcloud', 'auth', 'print-access-token'])
            code, out, err = await provider.run(['/opt/bin/credentials'], input=b'admin')

        A program for :meth:`fetch` to await, which gives its exit code, its
        standard output and its standard error.
        """
        return Steps.Command.new(args, input)

    def start(self, tx: Pyjo.Transaction.HTTP.object) -> Steps.Request:
        """::

            tx = await provider.start(provider.ua.build_tx('POST', url, form=body))

        A transaction for :meth:`fetch` to await, which :attr:`ua` starts, and
        which it gives back with its response.
        """
        return Steps.Request.new(tx)

    def steps(self) -> Steps.object[Credentials.object | None]:
        """::

            credentials = await provider.steps()
            credentials = yield from provider.steps()

        The :attr:`cached` credentials, or the ones of :meth:`fetch`, which it
        keeps, for a provider that gets its credentials with the ones of
        another, as an impersonated service account with the credentials of its
        source.
        """
        return Steps.Steps(self._steps())

    async def _steps(self) -> Credentials.object | None:
        if self.is_fresh():
            return self.cached
        credentials = await Steps.Steps(self.fetch())
        self.cached = credentials
        return credentials


def invalid(name: str, missing: Sequence[str]) -> Pyjo.Exception.object:
    """::

        raise Pyjo.GCP.Credentials.Provider.invalid('an authorized user', ['refresh_token'])

    The :mod:`Pyjo.Exception` of the credentials of the name without the
    fields that they need.
    """
    return Pyjo.Exception.new(f'Invalid credentials of {name}: no {", ".join(missing)}')


def parse_token(tx: Pyjo.Transaction.HTTP.object, name: str) -> dict[str, Any]:
    """::

        data = Pyjo.GCP.Credentials.Provider.parse_token(tx, 'an authorized user')

    The JSON object of the response of a token endpoint of OAuth 2.0, with
    ``access_token``, or a :mod:`Pyjo.Exception` of the credentials of the
    name, with ``error`` and ``error_description`` of OAuth 2.0, as
    google-auth has them, or the status of the response.
    """
    res = tx.res
    try:
        data: Any = res.json() if res.body else None
    except ValueError:
        data = None
    fields = cast(dict[str, Any], data) if isinstance(data, dict) else {}
    if res.code == 200 and isinstance(fields.get('access_token'), str):
        return fields
    if error := fields.get('error'):
        reason = f'{error}: {description}' if (description := fields.get('error_description')) else str(error)
    elif res.code == 200:
        reason = 'no access_token'
    else:
        reason = f'{res.code} {res.message or ""}'.strip()
    raise Pyjo.Exception.new(f'Cannot get the token of {name}: {reason}')


new = Pyjo_GCP_Credentials_Provider.new
object = Pyjo_GCP_Credentials_Provider
Provider = Pyjo_GCP_Credentials_Provider
