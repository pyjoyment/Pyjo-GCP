"""
Pyjo.GCP.Credentials.Impersonated - Credentials of an impersonated service account
==================================================================================
::

    from Pyjo.GCP.Credentials.Chain import Chain
    from Pyjo.GCP.Credentials.Impersonated import Impersonated

    provider = Impersonated(source=Chain(), target_principal='reader@myproject.iam.gserviceaccount.com',
                            scopes=['https://www.googleapis.com/auth/devstorage.read_only'])
    print(provider.credentials().account)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Credentials.Chain
    import Pyjo.GCP.Credentials.Impersonated

    provider = Pyjo.GCP.Credentials.Impersonated.new(
        source=Pyjo.GCP.Credentials.Chain.new(),
        target_principal='reader@myproject.iam.gserviceaccount.com',
        delegates=['projects/-/serviceAccounts/broker@myproject.iam.gserviceaccount.com'],
        lifetime=600,
    )
    provider.credentials_p().then(lambda credentials: print(credentials.expiration)).wait()

:mod:`Pyjo.GCP.Credentials.Impersonated` is the provider of the credentials
of a service account that the credentials of another provider, its source,
impersonate, with the role Service Account Token Creator on it: the access
token of ``generateAccessToken`` of the IAM Service Account Credentials API,
as ``gcloud --impersonate-service-account`` gets it.

A file of the type ``impersonated_service_account``, as
``gcloud auth application-default login --impersonate-service-account``
writes it, has the credentials of the source, of the type
``authorized_user``, ``service_account`` or
``external_account_authorized_user``, which
:mod:`Pyjo.GCP.Credentials.File` makes the provider of: ::

    {
      "type": "impersonated_service_account",
      "service_account_impersonation_url": "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/reader@myproject.iam.gserviceaccount.com:generateAccessToken",
      "delegates": [],
      "source_credentials": {
        "type": "authorized_user",
        "client_id": "764086051850-....apps.googleusercontent.com",
        "client_secret": "...",
        "refresh_token": "1//0g..."
      }
    }

The token of the source needs a scope of IAM, as
``https://www.googleapis.com/auth/cloud-platform``, the default one of
:mod:`Pyjo.GCP.Credentials.Chain`, or
``https://www.googleapis.com/auth/iam``, of the key of a service account of
a file. The endpoint of the API is the one of the universe domain of the
source, as google-auth has it, or the emulator of
``IAMCREDENTIALS_EMULATOR_HOST``, which the provider calls without a token,
as :mod:`Pyjo.GCP.Client` calls an emulator, so that a program tested
against emulators does not call Google. The token of the source comes of
its own provider, as the token endpoint of a key of a service account, which
no emulator replaces.

With a :attr:`subject`, the token is the one of the domain-wide delegation of
Google Workspace: the JWT of the grant of RFC 7523 that ``signJwt`` of the API
signs with the key of the service account that Google keeps.

See also
--------

:mod:`Pyjo.GCP.Credentials.Provider`, :mod:`Pyjo.GCP.Credentials.File`,
:mod:`Pyjo.GCP.Client`,
https://cloud.google.com/iam/docs/service-account-impersonation,
https://cloud.google.com/iam/docs/reference/credentials/rest.

Classes
-------
"""

import Pyjo.Date
import Pyjo.Exception
import Pyjo.JSON

from Pyjo.Util import url_escape

from .. import Call, Client, Config, Credentials, Error
from . import Provider, ServiceAccount

from collections.abc import Mapping, Sequence
from typing import Any, Self, cast


IAM_SCOPE = 'https://www.googleapis.com/auth/iam'
"""The scope of IAM, of the token of the key of a service account of a file that is the source."""

LIFETIME = 3600
"""The number of seconds that a token is valid, an hour, the most of the API without an organization policy."""


class Pyjo_GCP_Credentials_Impersonated(Provider.object):
    """
    :mod:`Pyjo.GCP.Credentials.Impersonated` inherits all attributes and
    methods from :mod:`Pyjo.GCP.Credentials.Provider` and implements the
    following new ones.
    """

    def __init__(
        self,
        *,
        source: Provider.object,
        target_principal: str,
        scopes: Sequence[str] | None = None,
        delegates: Sequence[str] | None = None,
        lifetime: int | None = LIFETIME,
        subject: str | None = None,
        quota_project: str | None = None,
        endpoint: str | None = None,
        url: str | None = None,
        token_uri: str = ServiceAccount.TOKEN_URI,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.Impersonated.new(source=source, target_principal=email)
            provider = Pyjo.GCP.Credentials.Impersonated.new(source=source, target_principal=email,
                                                             subject='admin@example.com')

        Construct a new :mod:`Pyjo.GCP.Credentials.Impersonated` object, with
        the options of :mod:`Pyjo.GCP.Credentials.Provider`.
        """
        super().__init__(**kwargs)

        self.source = source
        """::

            provider = provider.source

        The provider of the credentials that impersonate the service account.
        """

        self.target_principal = target_principal
        """::

            email = provider.target_principal

        The email of the service account that is impersonated.
        """

        self.scopes = list(scopes) if scopes else [Credentials.CLOUD_PLATFORM]
        """::

            scopes = provider.scopes

        The scopes of the token,
        ``https://www.googleapis.com/auth/cloud-platform`` by default.
        """

        self.delegates = list(delegates) if delegates else []
        """::

            delegates = provider.delegates

        The service accounts of a chain of delegation, as
        ``projects/-/serviceAccounts/broker@myproject.iam.gserviceaccount.com``,
        each with the role Service Account Token Creator on the next one,
        and the last one on :attr:`target_principal`, or none, as the source
        has it on :attr:`target_principal` itself.
        """

        self.lifetime = lifetime or LIFETIME
        """::

            seconds = provider.lifetime

        The number of seconds that the token is valid, 3600 by default.
        """

        self.subject = subject
        """::

            email = provider.subject

        The email of a user that the service account acts as, of the
        domain-wide delegation of Google Workspace, or ``None``.
        """

        self.quota_project = quota_project
        """::

            project = provider.quota_project

        The quota project of the credentials, or ``None``.
        """

        self.endpoint = endpoint
        """::

            url = provider.endpoint

        The URL of the endpoint of the IAM Service Account Credentials API,
        which comes over the emulator of ``IAMCREDENTIALS_EMULATOR_HOST`` and
        :attr:`url`, or ``None``, for ``https://iamcredentials.<universe domain>``
        of the universe domain of the source.
        """

        self.url = url
        """::

            url = provider.url

        The URL of ``generateAccessToken`` of the service account, as
        ``service_account_impersonation_url`` of the credentials of an
        external account has it, without an :attr:`endpoint` and an emulator
        of ``IAMCREDENTIALS_EMULATOR_HOST``, or ``None``.
        """

        self.token_uri = token_uri
        """::

            url = provider.token_uri

        The token endpoint of OAuth 2.0 of the grant of a :attr:`subject`,
        ``https://oauth2.googleapis.com/token``.
        """

    @classmethod
    def from_info(cls, info: Mapping[str, Any], *, source: Provider.object, **kwargs: Any) -> Self:
        """::

            provider = Impersonated.from_info(info, source=source)
            provider = Impersonated.from_info(info, source=source, scopes=scopes, ua=ua)

        A new provider of the JSON object of a file of the type
        ``impersonated_service_account``, with the provider of its
        ``source_credentials``, with the service account of
        ``service_account_impersonation_url``, ``delegates``, ``scopes`` and
        ``quota_project_id`` of the file, and the arguments over them, or a
        :mod:`Pyjo.Exception` of a file without a service account in the URL.
        The endpoint of the URL is not the one of the provider, as google-auth
        has it.
        """
        url = info.get('service_account_impersonation_url')
        url = url if isinstance(url, str) else ''
        start, end = url.rfind('/'), url.find(':generateAccessToken')
        if start == -1 or end == -1 or start > end:
            raise Pyjo.Exception.new(
                f'Invalid credentials of an impersonated service account: no service account in {url!r}'
            )
        values: dict[str, Any] = {
            'target_principal': url[start + 1 : end],
            'delegates': info.get('delegates'),
            'scopes': info.get('scopes'),
            'quota_project': info.get('quota_project_id'),
        }
        return cls(source=source, **{**values, **{name: value for name, value in kwargs.items() if value is not None}})

    async def fetch(self) -> Credentials.object:
        """::

            credentials = await provider.fetch()

        The access token of the service account, with the credentials of the
        source, or of the grant of the JWT of a :attr:`subject`.
        """
        source = await self.source.steps()
        if source is None:
            raise self._error('no credentials of the source')
        universe = source.universe_domain or Config.UNIVERSE_DOMAIN
        if self.subject:
            token, expiration = await self._grant(source, universe)
        else:
            body = {'scope': self.scopes, 'lifetime': f'{self.lifetime}s'}
            data = await self._call(source, universe, 'generateAccessToken', body)
            token, expire_time = data.get('accessToken'), data.get('expireTime')
            if not isinstance(token, str) or not isinstance(expire_time, str):
                raise self._error('no accessToken or expireTime')
            expiration = Credentials.parse_time(expire_time)
        return Credentials.new(
            token=token,
            expiration=expiration,
            project=source.project,
            quota_project=self.quota_project,
            universe_domain=universe,
            account=self.target_principal,
            provider='impersonated_service_account',
        )

    async def _call(
        self, source: Credentials.object, universe: str, method: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        if self.delegates:
            body['delegates'] = self.delegates
        account = url_escape(self.target_principal, r'^A-Za-z0-9\-._~@')
        path = f'/v1/projects/-/serviceAccounts/{account}:{method}'
        config, endpoint = Config.new(), self.endpoint
        if endpoint is None and config.emulator_host('iamcredentials') is None:
            if method == 'generateAccessToken' and self.url is not None:
                endpoint, path = _split(self.url)
            else:
                endpoint = f'https://iamcredentials.{universe}'
        client = Client.new(
            service='iamcredentials', endpoint=endpoint, config=config, credentials=self.source, ua=self.ua
        )
        call = Call.new('POST', path, body)
        try:
            data = await client.steps(call, source)
        except Error.object as e:
            raise self._error(e.message) from e
        if not isinstance(data, dict):
            raise self._error(f'no JSON object of {method}')
        return cast(dict[str, Any], data)

    async def _grant(self, source: Credentials.object, universe: str) -> tuple[str, Any]:
        if universe != Config.UNIVERSE_DOMAIN:
            raise self._error(f'no domain-wide delegation in the universe domain {universe}')
        now = int(Pyjo.Date.new().epoch or 0)
        claims = {
            'iss': self.target_principal,
            'scope': ' '.join(self.scopes),
            'sub': self.subject,
            'aud': ServiceAccount.TOKEN_URI,
            'iat': now,
            'exp': now + ServiceAccount.LIFETIME,
        }
        data = await self._call(source, universe, 'signJwt', {'payload': Pyjo.JSON.to_json(claims)})
        if not isinstance(assertion := data.get('signedJwt'), str):
            raise self._error('no signedJwt')
        form = {'grant_type': ServiceAccount.GRANT_TYPE, 'assertion': assertion}
        tx = await self.start(self.ua.build_tx('POST', self.token_uri, form=form))
        data = Provider.parse_token(tx, f'the impersonated service account {self.target_principal} of {self.subject}')
        return data['access_token'], Credentials.expiration_in(data['expires_in']) if 'expires_in' in data else None

    def _error(self, reason: str) -> Pyjo.Exception.object:
        return Pyjo.Exception.new(
            f'Cannot get the token of the impersonated service account {self.target_principal}: {reason}'
        )


# The endpoint and the path of a URL, of an empty endpoint of a relative one
def _split(url: str) -> tuple[str, str]:
    start = url.find('://')
    slash = url.find('/', start + 3) if start != -1 else 0
    return (url, '/') if slash == -1 else (url[:slash], url[slash:])


new = Pyjo_GCP_Credentials_Impersonated.new
object = Pyjo_GCP_Credentials_Impersonated
Impersonated = Pyjo_GCP_Credentials_Impersonated
