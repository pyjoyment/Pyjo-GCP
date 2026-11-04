"""
Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser - Credentials of a user of a workforce pool
==============================================================================================
::

    import Pyjo.GCP.Config
    import Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser

    config = Pyjo.GCP.Config.new()
    info = config.credentials_info(config.adc_file())
    provider = Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser.ExternalAccountAuthorizedUser.from_info(info)
    print(provider.credentials().token)

:mod:`Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser` is the provider of
the credentials of a user of Workforce Identity Federation, of a file of the
type ``external_account_authorized_user``, as
``gcloud auth application-default login --login-config`` writes it: the
refresh token of the user, which the Security Token Service of Google
exchanges for an access token, with the basic authentication of the OAuth
client of the workforce pool. ::

    {
      "type": "external_account_authorized_user",
      "audience": "//iam.googleapis.com/locations/global/workforcePools/pool/providers/oidc",
      "client_id": "...",
      "client_secret": "...",
      "refresh_token": "...",
      "token_url": "https://sts.googleapis.com/v1/oauthtoken",
      "token_info_url": "https://sts.googleapis.com/v1/introspect",
      "universe_domain": "googleapis.com"
    }

An access token of the file, with ``token`` and ``expiry``, is the first one,
until it is about to expire, and a file without the refresh token has only
that one. The token has the scopes of the login, as the request of the
refresh token has none, as google-auth has it, and a new refresh token of
the response replaces the one of the provider.

See also
--------

:mod:`Pyjo.GCP.Credentials.Provider`, :mod:`Pyjo.GCP.Credentials.File`,
https://google.aip.dev/auth/4117,
https://cloud.google.com/iam/docs/workforce-obtaining-short-lived-credentials.

Classes
-------
"""

import Pyjo.Exception

from Pyjo.Util import b64_encode

from .. import Config, Credentials
from . import Provider

import datetime

from collections.abc import Mapping
from typing import Any, Self


class Pyjo_GCP_Credentials_ExternalAccountAuthorizedUser(Provider.object):
    """
    :mod:`Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser` inherits all
    attributes and methods from :mod:`Pyjo.GCP.Credentials.Provider` and
    implements the following new ones.
    """

    def __init__(
        self,
        *,
        refresh_token: str | None = None,
        token_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        audience: str | None = None,
        token: str | None = None,
        expiration: datetime.datetime | None = None,
        quota_project: str | None = None,
        universe_domain: str | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser.new(
                refresh_token=refresh_token, token_url='https://sts.googleapis.com/v1/oauthtoken',
                client_id=client_id, client_secret=client_secret)

        Construct a new :mod:`Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser`
        object, with the options of :mod:`Pyjo.GCP.Credentials.Provider`, or
        a :mod:`Pyjo.Exception` without the fields of a refresh or a token.
        """
        super().__init__(**kwargs)

        refresh = {'refresh_token': refresh_token, 'token_url': token_url, 'client_id': client_id,
                   'client_secret': client_secret}  # fmt: skip
        if not token and (missing := [name for name, value in refresh.items() if not value]):
            raise Provider.invalid('an external account of a user', missing)

        self.refresh_token = refresh_token
        """::

            refresh_token = provider.refresh_token

        The refresh token of the user, or ``None``.
        """

        self.token_url = token_url
        """::

            url = provider.token_url

        The token endpoint of the refresh, as
        ``https://sts.googleapis.com/v1/oauthtoken``, or ``None``.
        """

        self.client_id = client_id
        """::

            client_id = provider.client_id

        The ID of the OAuth client of the workforce pool, or ``None``.
        """

        self.client_secret = client_secret
        """::

            secret = provider.client_secret

        The secret of the OAuth client, or ``None``.
        """

        self.audience = audience
        """::

            audience = provider.audience

        The resource name of the provider of the workforce pool, or
        ``None``.
        """

        self.quota_project = quota_project
        """::

            project = provider.quota_project

        The quota project of the credentials, or ``None``.
        """

        self.universe_domain = universe_domain or Config.UNIVERSE_DOMAIN
        """::

            domain = provider.universe_domain

        The universe domain, ``googleapis.com`` by default.
        """

        if token:
            self.cached = self._credentials(token, expiration)

    @classmethod
    def from_info(cls, info: Mapping[str, Any], **kwargs: Any) -> Self:
        """::

            provider = ExternalAccountAuthorizedUser.from_info(info)
            provider = ExternalAccountAuthorizedUser.from_info(info, ua=ua)

        A new provider of the JSON object of a file of the type
        ``external_account_authorized_user``, with the fields of the file and
        the arguments over them.
        """
        expiry = info.get('expiry')
        values: dict[str, Any] = {
            'refresh_token': info.get('refresh_token'),
            'token_url': info.get('token_url'),
            'client_id': info.get('client_id'),
            'client_secret': info.get('client_secret'),
            'audience': info.get('audience'),
            'token': info.get('token'),
            'expiration': Credentials.parse_time(expiry) if isinstance(expiry, str) and expiry else None,
            'quota_project': info.get('quota_project_id'),
            'universe_domain': info.get('universe_domain'),
        }
        return cls(**{**values, **kwargs})

    async def fetch(self) -> Credentials.object:
        """::

            credentials = await provider.fetch()

        The access token of the refresh token, or a :mod:`Pyjo.Exception`
        without one.
        """
        if not (self.refresh_token and self.token_url and self.client_id and self.client_secret):
            raise Pyjo.Exception.new(
                'Cannot get the token of an external account of a user: no refresh_token, token_url, client_id or'
                ' client_secret'
            )
        basic = b64_encode(f'{self.client_id}:{self.client_secret}'.encode(), '')
        form = {'grant_type': 'refresh_token', 'refresh_token': self.refresh_token}
        tx = await self.start(self.ua.build_tx('POST', self.token_url, {'Authorization': f'Basic {basic}'}, form=form))
        data = Provider.parse_token(tx, 'an external account of a user')
        if isinstance(refresh_token := data.get('refresh_token'), str) and refresh_token:
            self.refresh_token = refresh_token
        expires_in = data.get('expires_in')
        return self._credentials(
            data['access_token'], Credentials.expiration_in(expires_in) if expires_in is not None else None
        )

    def _credentials(self, token: str, expiration: datetime.datetime | None) -> Credentials.object:
        return Credentials.new(
            token=token,
            expiration=expiration,
            quota_project=self.quota_project,
            universe_domain=self.universe_domain,
            provider='external_account_authorized_user',
        )


new = Pyjo_GCP_Credentials_ExternalAccountAuthorizedUser.new
object = Pyjo_GCP_Credentials_ExternalAccountAuthorizedUser
ExternalAccountAuthorizedUser = Pyjo_GCP_Credentials_ExternalAccountAuthorizedUser
