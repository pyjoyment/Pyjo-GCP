"""
Pyjo.GCP.Credentials.ServiceAccount - Credentials of the key of a service account
=================================================================================
::

    from Pyjo.GCP.Credentials.ServiceAccount import ServiceAccount

    provider = ServiceAccount.from_info(info, scopes=['https://www.googleapis.com/auth/devstorage.read_only'])
    print(provider.credentials().token)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Config
    import Pyjo.GCP.Credentials.ServiceAccount

    info = Pyjo.GCP.Config.new().credentials_info('/etc/gcloud/key.json')

    # A self-signed JWT of AIP-4111, without a request
    provider = Pyjo.GCP.Credentials.ServiceAccount.ServiceAccount.from_info(info, self_signed=True)
    provider.credentials_p().then(lambda credentials: print(credentials.expiration)).wait()

:mod:`Pyjo.GCP.Credentials.ServiceAccount` is the provider of the
credentials of the key of a service account, of a file of the type
``service_account``, as the console of Google Cloud and
``gcloud iam service-accounts keys create`` make it, of AIP-4112: ::

    {
      "type": "service_account",
      "project_id": "myproject",
      "private_key_id": "3c5a...",
      "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
      "client_email": "reader@myproject.iam.gserviceaccount.com",
      "token_uri": "https://oauth2.googleapis.com/token",
      "universe_domain": "googleapis.com"
    }

The token is the access token of the JSON Web Token bearer grant of RFC 7523,
a JWT of RS256 of :mod:`Pyjo.GCP.RSA` with the scopes, which the token
endpoint exchanges, or, with ``self_signed``, the JWT itself, of AIP-4111,
which the APIs of Google take as a token, without a request. A key of another
universe domain than ``googleapis.com`` has a self-signed JWT always, as
google-auth has it.

See also
--------

:mod:`Pyjo.GCP.Credentials.Provider`, :mod:`Pyjo.GCP.Credentials.File`,
:mod:`Pyjo.GCP.RSA`, https://google.aip.dev/auth/4111,
https://google.aip.dev/auth/4112, :rfc:`7523`.

Classes
-------
"""

import Pyjo.Date

from .. import RSA, Config, Credentials
from . import Provider

from collections.abc import Mapping, Sequence
from typing import Any, Self


TOKEN_URI = 'https://oauth2.googleapis.com/token'
"""The token endpoint of OAuth 2.0 of Google, the audience of the grant of the key."""

GRANT_TYPE = 'urn:ietf:params:oauth:grant-type:jwt-bearer'
"""The grant type of RFC 7523."""

LIFETIME = 3600
"""The number of seconds that a JWT of the key is valid, an hour, as google-auth has it."""


class Pyjo_GCP_Credentials_ServiceAccount(Provider.object):
    """
    :mod:`Pyjo.GCP.Credentials.ServiceAccount` inherits all attributes and
    methods from :mod:`Pyjo.GCP.Credentials.Provider` and implements the
    following new ones.
    """

    def __init__(
        self,
        *,
        client_email: str,
        private_key: str,
        private_key_id: str | None = None,
        token_uri: str | None = None,
        scopes: Sequence[str] | None = None,
        subject: str | None = None,
        self_signed: bool = False,
        project: str | None = None,
        quota_project: str | None = None,
        universe_domain: str | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.ServiceAccount.new(client_email=email, private_key=pem)
            provider = Pyjo.GCP.Credentials.ServiceAccount.new(client_email=email, private_key=pem,
                                                               subject='admin@example.com')

        Construct a new :mod:`Pyjo.GCP.Credentials.ServiceAccount` object,
        with the options of :mod:`Pyjo.GCP.Credentials.Provider`, or a
        :mod:`Pyjo.Exception` of an invalid key.
        """
        super().__init__(**kwargs)

        self.client_email = client_email
        """::

            email = provider.client_email

        The email of the service account.
        """

        self.key = RSA.from_pem(private_key)
        """::

            key = provider.key

        The private key of the service account, a :mod:`Pyjo.GCP.RSA` object.
        """

        self.private_key_id = private_key_id
        """::

            key_id = provider.private_key_id

        The ID of the key, ``kid`` of the JWT, or ``None``.
        """

        self.token_uri = token_uri or TOKEN_URI
        """::

            url = provider.token_uri

        The token endpoint of OAuth 2.0 of the grant, of the key, or
        ``https://oauth2.googleapis.com/token``.
        """

        self.scopes = list(scopes) if scopes else [Credentials.CLOUD_PLATFORM]
        """::

            scopes = provider.scopes

        The scopes of the token,
        ``https://www.googleapis.com/auth/cloud-platform`` by default.
        """

        self.subject = subject
        """::

            email = provider.subject

        The email of a user that the service account acts as, of the
        domain-wide delegation of Google Workspace, or ``None``.
        """

        self.universe_domain = universe_domain
        """::

            domain = provider.universe_domain

        The universe domain of the key, or ``None``.
        """

        self.self_signed = self_signed or bool(universe_domain and universe_domain != Config.UNIVERSE_DOMAIN)
        """::

            boolean = provider.self_signed

        Whether the token is a self-signed JWT of AIP-4111, rather than the
        access token of the grant, false by default, and true for a key of
        another universe domain than ``googleapis.com``. A :attr:`subject`
        has the grant always.
        """

        self.project = project
        """::

            project = provider.project

        The project of the key, or ``None``.
        """

        self.quota_project = quota_project
        """::

            project = provider.quota_project

        The quota project of the credentials, or ``None``.
        """

    @classmethod
    def from_info(cls, info: Mapping[str, Any], **kwargs: Any) -> Self:
        """::

            provider = ServiceAccount.from_info(info)
            provider = ServiceAccount.from_info(info, scopes=scopes, ua=ua)

        A new provider of the JSON object of a file of the type
        ``service_account``, with ``private_key_id``, ``project_id`` and
        ``universe_domain`` of the file, and the arguments over them, or a
        :mod:`Pyjo.Exception` of a file without ``client_email``,
        ``private_key`` or ``token_uri``, as google-auth requires them.
        """
        missing = [name for name in ('client_email', 'private_key', 'token_uri') if not info.get(name)]
        if missing:
            raise Provider.invalid('a service account', missing)
        values: dict[str, Any] = {
            'client_email': info['client_email'],
            'private_key': info['private_key'],
            'private_key_id': info.get('private_key_id'),
            'token_uri': info['token_uri'],
            'project': info.get('project_id'),
            'universe_domain': info.get('universe_domain'),
        }
        return cls(**{**values, **kwargs})

    def assertion(self, now: int | None = None) -> str:
        """::

            jwt = provider.assertion()

        The JWT of the grant of RFC 7523, with the email of the service
        account, the scopes, the :attr:`subject`, and the audience of
        ``https://oauth2.googleapis.com/token``, as google-auth has it, also
        for another :attr:`token_uri`.
        """
        iat = now if now is not None else int(Pyjo.Date.new().epoch or 0)
        claims: dict[str, Any] = {
            'iat': iat,
            'exp': iat + LIFETIME,
            'iss': self.client_email,
            'aud': TOKEN_URI,
            'scope': ' '.join(self.scopes),
        }
        if self.subject:
            claims['sub'] = self.subject
        return self.key.jwt(claims, key_id=self.private_key_id)

    async def fetch(self) -> Credentials.object:
        """::

            credentials = await provider.fetch()

        The self-signed JWT, or the access token of the grant.
        """
        now = int(Pyjo.Date.new().epoch or 0)
        if self.self_signed and not self.subject:
            claims = {
                'iss': self.client_email,
                'sub': self.client_email,
                'iat': now,
                'exp': now + LIFETIME,
                'scope': ' '.join(self.scopes),
            }
            token = self.key.jwt(claims, key_id=self.private_key_id)
            return self._credentials(token, Pyjo.Date.new(now + LIFETIME).to_datetime())
        form = {'grant_type': GRANT_TYPE, 'assertion': self.assertion(now)}
        tx = await self.start(self.ua.build_tx('POST', self.token_uri, form=form))
        data = Provider.parse_token(tx, f'the service account {self.client_email}')
        expiration = Credentials.expiration_in(data['expires_in']) if 'expires_in' in data else None
        return self._credentials(data['access_token'], expiration)

    def _credentials(self, token: str, expiration: Any) -> Credentials.object:
        return Credentials.new(
            token=token,
            expiration=expiration,
            project=self.project,
            quota_project=self.quota_project,
            universe_domain=self.universe_domain,
            account=self.client_email,
            provider='service_account',
        )


new = Pyjo_GCP_Credentials_ServiceAccount.new
object = Pyjo_GCP_Credentials_ServiceAccount
ServiceAccount = Pyjo_GCP_Credentials_ServiceAccount
