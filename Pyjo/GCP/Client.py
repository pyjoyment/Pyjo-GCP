"""
Pyjo.GCP.Client - Client of a JSON API of Google Cloud
======================================================
::

    from Pyjo.GCP.Call import Call
    from Pyjo.GCP.Client import Client

    storage = Client(service='storage')
    print(storage.call(Call('GET', '/storage/v1/b', query={'project': 'myproject'})))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Call
    import Pyjo.GCP.Client

    storage = Pyjo.GCP.Client.new(service='storage', scopes=['https://www.googleapis.com/auth/devstorage.read_only'])
    call = Pyjo.GCP.Call.new('GET', '/storage/v1/b/mybucket/o', query={'prefix': 'docs/', 'delimiter': '/'})
    storage.call_p(call).then(lambda objects: print(objects.get('prefixes'))).wait()

:mod:`Pyjo.GCP.Client` calls a JSON API of Google Cloud, of a service, with
the calls of :mod:`Pyjo.GCP.Call`: it authorizes the request of a call with
the access token of :mod:`Pyjo.GCP.Credentials`, which
:mod:`Pyjo.GCP.Credentials.Chain` finds by default, as the Application
Default Credentials, starts it with :mod:`Pyjo.UserAgent`, blocking or
non-blocking, and gives the result of its response, or raises the
:mod:`Pyjo.GCP.Error` that Google Cloud responds with.

The endpoint of the service is :attr:`~Pyjo_GCP_Client.endpoint`, or the one
of :meth:`~Pyjo.GCP.Config.Pyjo_GCP_Config.endpoint_url`, as
``https://storage.googleapis.com``, of the universe domain, or of the
emulator of ``<SERVICE>_EMULATOR_HOST``, as ``STORAGE_EMULATOR_HOST``, which
the client calls without a token, as the client libraries of Google do. ::

    # fake-gcs-server, without credentials
    os.environ['STORAGE_EMULATOR_HOST'] = 'localhost:4443'
    storage = Pyjo.GCP.Client.new(service='storage')

A provider of credentials calls an API of Google Cloud with
:meth:`~Pyjo_GCP_Client.steps`, which :mod:`Pyjo.GCP.Steps` runs with its
own steps, as an impersonated service account with the credentials of its
source: ::

    async def fetch(self):
        source = await self.source.steps()
        token = await iam.steps(Call('POST', f'/v1/projects/-/serviceAccounts/{email}:generateAccessToken', ...),
                                source)

See also
--------

:mod:`Pyjo.GCP.Call`, :mod:`Pyjo.GCP.Error`, :mod:`Pyjo.GCP.Credentials`,
https://google.aip.dev/auth/4110.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.Promise
import Pyjo.URL
import Pyjo.UserAgent

from . import Call, Config, Credentials, Steps
from .Credentials import Provider

from collections.abc import Sequence
from typing import Any, Literal


class Pyjo_GCP_Client(Pyjo.Base.object):
    """
    :mod:`Pyjo.GCP.Client` inherits all attributes and methods from
    :mod:`Pyjo.Base` and implements the following new ones.
    """

    def __init__(
        self,
        *,
        service: str,
        endpoint: str | None = None,
        anonymous: bool | None = None,
        config: Config.object | None = None,
        credentials: Provider.object | None = None,
        scopes: Sequence[str] | None = None,
        quota_project: str | Literal[False] | None = None,
        ua: Pyjo.UserAgent.object | None = None,
    ) -> None:
        """::

            client = Pyjo.GCP.Client.new(service='storage')
            client = Pyjo.GCP.Client.new(service='iamcredentials', credentials=provider)
            client = Pyjo.GCP.Client.new(service='storage', endpoint='http://127.0.0.1:4443', anonymous=True)

        Construct a new :mod:`Pyjo.GCP.Client` object.
        """
        self.service = service
        """::

            service = client.service

        The name of the service, as ``storage``, the prefix of its endpoint.
        """

        self.config = config or Config.new()
        """::

            config = client.config

        The configuration of the endpoint and the default credentials, a new
        :mod:`Pyjo.GCP.Config` object by default.
        """

        self.endpoint = endpoint
        """::

            url = client.endpoint
            client.endpoint = 'http://127.0.0.1:4443'

        The URL of the endpoint, which comes over the one of :attr:`config`,
        also a relative one, as an empty one of the server of :attr:`ua`, or
        ``None``.
        """

        emulator = endpoint is None and self.config.emulator_host(service) is not None
        self.anonymous = emulator if anonymous is None else anonymous
        """::

            boolean = client.anonymous

        Send the requests without a token, as to an emulator of
        ``<SERVICE>_EMULATOR_HOST``, which it is by default, or to a public
        bucket of Cloud Storage.
        """

        self.ua = ua or Pyjo.UserAgent.new()
        """::

            ua = client.ua

        The user agent of the requests, a new :mod:`Pyjo.UserAgent` object by
        default.
        """

        self.quota_project = quota_project
        """::

            project = client.quota_project
            client.quota_project = False

        The quota project of ``x-goog-user-project``, over the one of the
        credentials, ``False`` for none, or ``None``, for the one of the
        credentials, as ``client_options.quota_project_id`` of the client
        libraries of Google. A client of Cloud Storage that serves the
        objects of its own bucket needs none: Cloud Storage bills a request
        with one to that project, as the one of a bucket of requester pays,
        and gives its response ``Cache-Control: no-cache`` then.
        """

        # Chain imports the providers of the files, of which the impersonated service account imports this module
        from .Credentials import Chain

        self.credentials: Provider.object = credentials or Chain.new(config=self.config, scopes=scopes, ua=self.ua)
        """::

            provider = client.credentials

        The provider of the credentials, a new
        :mod:`Pyjo.GCP.Credentials.Chain` object of :attr:`config` and of the
        scopes of the argument by default.
        """

    def call(self, call: Call.object) -> Any:
        """::

            result = client.call(Pyjo.GCP.Call.new('GET', '/storage/v1/b/mybucket'))

        Call a method of the API, blocking, and give its result, or raise its
        :mod:`Pyjo.GCP.Error`.
        """
        return self.steps(call).run(self.ua)

    def call_p(self, call: Call.object) -> Pyjo.Promise.object:
        """::

            promise = client.call_p(Pyjo.GCP.Call.new('GET', '/storage/v1/b/mybucket'))

        Same as :meth:`call`, but non-blocking, and returns a
        :mod:`Pyjo.Promise` object. The credentials come of
        :meth:`~Pyjo.GCP.Credentials.Provider.Pyjo_GCP_Credentials_Provider.credentials_p`,
        so that the calls while the provider gets them wait for them once.
        """
        if self.anonymous:
            return self.steps(call).run_p(self.ua)

        def authorized(credentials: Credentials.object | None) -> Pyjo.Promise.object:
            return self.steps(call, _required(credentials)).run_p(self.ua)

        return self.credentials.credentials_p().then(authorized)

    def endpoint_url(self) -> str:
        """::

            url = client.endpoint_url()

        The URL of the endpoint, :attr:`endpoint`, or the one of
        :attr:`config`.
        """
        return self.endpoint if self.endpoint is not None else self.config.endpoint_url(self.service)

    def headers(self, credentials: Credentials.object) -> dict[str, str]:
        """::

            headers = client.headers(credentials)

        The headers of a request with credentials, ``Authorization`` of the
        token, and ``x-goog-user-project`` of the quota project of
        :attr:`quota_project` or of the credentials, as google-auth has them,
        or a :mod:`Pyjo.Exception` of credentials of
        another universe domain than the one of the endpoint.
        """
        domain = credentials.universe_domain
        if self.endpoint is None and domain and domain != (universe := self.config.universe_domain()):
            raise Pyjo.Exception.new(
                f'The universe domain of the credentials of Google Cloud {domain} is not the one of {self.service}'
                f' {universe}: GOOGLE_CLOUD_UNIVERSE_DOMAIN'
            )
        headers = {'Authorization': f'Bearer {credentials.token}'}
        quota_project = credentials.quota_project if self.quota_project is None else self.quota_project
        if isinstance(quota_project, str) and quota_project:
            headers['x-goog-user-project'] = quota_project
        return headers

    def steps(self, call: Call.object, credentials: Credentials.object | None = None) -> Steps.object[Any]:
        """::

            result = await client.steps(call)
            result = await client.steps(call, credentials)

        The :mod:`Pyjo.GCP.Steps` of a call, of a provider of credentials,
        with credentials, or those of :attr:`credentials` by default.
        """
        return Steps.Steps(self._steps(call, credentials))

    async def _steps(self, call: Call.object, credentials: Credentials.object | None) -> Any:
        if not self.anonymous and credentials is None:
            credentials = _required(await self.credentials.steps())
        headers = self.headers(credentials) if credentials is not None and not self.anonymous else {}
        tx = call.build_tx(self.ua, Pyjo.URL.new(self.endpoint_url()))
        for name, value in headers.items():
            tx.req.headers.header(name, value)
        return call.result(await Steps.Request.new(tx, self.ua))


def _required(credentials: Credentials.object | None) -> Credentials.object:
    if credentials is None:
        raise Pyjo.Exception.new(
            'No credentials of Google Cloud: GOOGLE_APPLICATION_CREDENTIALS, gcloud auth application-default login,'
            ' or the metadata server'
        )
    return credentials


new = Pyjo_GCP_Client.new
object = Pyjo_GCP_Client
Client = Pyjo_GCP_Client
