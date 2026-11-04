"""
Pyjo.GCP.Credentials.AuthorizedUser - Credentials of a user of gcloud
=====================================================================
::

    from Pyjo.GCP.Credentials.AuthorizedUser import AuthorizedUser

    provider = AuthorizedUser(client_id='764086051850-...', client_secret='...',
                              refresh_token='1//0g...')
    print(provider.credentials().token)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Config
    import Pyjo.GCP.Credentials.AuthorizedUser

    config = Pyjo.GCP.Config.new()
    info = config.credentials_info(config.adc_file())
    provider = Pyjo.GCP.Credentials.AuthorizedUser.AuthorizedUser.from_info(info)
    provider.credentials_p().then(lambda credentials: print(credentials.expiration)).wait()

:mod:`Pyjo.GCP.Credentials.AuthorizedUser` is the provider of the
credentials of a user, of a file of the type ``authorized_user``, as
``gcloud auth application-default login`` writes it: the refresh token of
the user, which the token endpoint of OAuth 2.0 of Google exchanges for an
access token, with the client of gcloud. ::

    {
      "type": "authorized_user",
      "client_id": "764086051850-....apps.googleusercontent.com",
      "client_secret": "...",
      "refresh_token": "1//0g...",
      "quota_project_id": "myproject",
      "account": "me@example.com",
      "universe_domain": "googleapis.com"
    }

The token has the scopes of the login, as the request of the refresh token
has none, as google-auth does for the Application Default Credentials. A
new refresh token of the response replaces the one of the provider.

See also
--------

:mod:`Pyjo.GCP.Credentials.Provider`, :mod:`Pyjo.GCP.Credentials.File`,
https://google.aip.dev/auth/4113.

Classes
-------
"""

from .. import Credentials
from . import Provider

from collections.abc import Mapping
from typing import Any, Self


TOKEN_URI = 'https://oauth2.googleapis.com/token'
"""The token endpoint of OAuth 2.0 of Google."""


class Pyjo_GCP_Credentials_AuthorizedUser(Provider.object):
    """
    :mod:`Pyjo.GCP.Credentials.AuthorizedUser` inherits all attributes and
    methods from :mod:`Pyjo.GCP.Credentials.Provider` and implements the
    following new ones.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        token_uri: str | None = None,
        quota_project: str | None = None,
        universe_domain: str | None = None,
        account: str | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.AuthorizedUser.new(client_id=client_id, client_secret=client_secret,
                                                               refresh_token=refresh_token)

        Construct a new :mod:`Pyjo.GCP.Credentials.AuthorizedUser` object,
        with the options of :mod:`Pyjo.GCP.Credentials.Provider`.
        """
        super().__init__(**kwargs)

        self.client_id = client_id
        """::

            client_id = provider.client_id

        The ID of the client of OAuth 2.0, as the one of gcloud.
        """

        self.client_secret = client_secret
        """::

            client_secret = provider.client_secret

        The secret of the client of OAuth 2.0.
        """

        self.refresh_token = refresh_token
        """::

            refresh_token = provider.refresh_token

        The refresh token of the user.
        """

        self.token_uri = token_uri or TOKEN_URI
        """::

            url = provider.token_uri

        The token endpoint of OAuth 2.0, ``https://oauth2.googleapis.com/token``
        by default.
        """

        self.quota_project = quota_project
        """::

            project = provider.quota_project

        The quota project of the credentials, or ``None``.
        """

        self.universe_domain = universe_domain
        """::

            domain = provider.universe_domain

        The universe domain of the credentials, or ``None``.
        """

        self.account = account
        """::

            account = provider.account

        The email of the user, or ``None``.
        """

    @classmethod
    def from_info(cls, info: Mapping[str, Any], **kwargs: Any) -> Self:
        """::

            provider = AuthorizedUser.from_info(info)
            provider = AuthorizedUser.from_info(info, quota_project='myproject', ua=ua)

        A new provider of the JSON object of a file of the type
        ``authorized_user``, with ``quota_project_id``, ``universe_domain``,
        ``account`` and ``token_uri`` of the file, and the arguments over
        them, or a :mod:`Pyjo.Exception` of a file without
        ``client_id``, ``client_secret`` or ``refresh_token``.
        """
        missing = [name for name in ('client_id', 'client_secret', 'refresh_token') if not info.get(name)]
        if missing:
            raise Provider.invalid('an authorized user', missing)
        values: dict[str, Any] = {
            'client_id': info['client_id'],
            'client_secret': info['client_secret'],
            'refresh_token': info['refresh_token'],
            'token_uri': info.get('token_uri'),
            'quota_project': info.get('quota_project_id'),
            'universe_domain': info.get('universe_domain'),
            'account': info.get('account') or None,
        }
        return cls(**{**values, **kwargs})

    async def fetch(self) -> Credentials.object:
        """::

            credentials = await provider.fetch()

        The access token of the refresh token.
        """
        form = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
        }
        tx = await self.start(self.ua.build_tx('POST', self.token_uri, form=form))
        data = Provider.parse_token(tx, 'an authorized user')
        if isinstance(refresh_token := data.get('refresh_token'), str) and refresh_token:
            self.refresh_token = refresh_token
        return Credentials.new(
            token=data['access_token'],
            expiration=Credentials.expiration_in(data['expires_in']) if 'expires_in' in data else None,
            quota_project=self.quota_project,
            universe_domain=self.universe_domain,
            account=self.account,
            provider='authorized_user',
        )


new = Pyjo_GCP_Credentials_AuthorizedUser.new
object = Pyjo_GCP_Credentials_AuthorizedUser
AuthorizedUser = Pyjo_GCP_Credentials_AuthorizedUser
