"""
Pyjo.GCP.Credentials.ExternalAccount - Credentials of an external account
=========================================================================
::

    from Pyjo.GCP.Credentials.ExternalAccount import ExternalAccount

    class Supplier(ExternalAccount):
        async def subject_token(self):
            return await my_token_of_another_identity_provider()

    provider = Supplier(
        audience='//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/oidc',
        subject_token_type='urn:ietf:params:oauth:token-type:jwt',
    )
    print(provider.credentials().token)

:mod:`Pyjo.GCP.Credentials.ExternalAccount` is the base class of the
providers of the credentials of an external account of Workload Identity
Federation and Workforce Identity Federation, of a file of the type
``external_account``, of AIP-4117: the token of another identity provider, a
subject token, which the Security Token Service of Google exchanges for an
access token, as :rfc:`8693` has it, and which a subclass gets in
:meth:`~Pyjo_GCP_Credentials_ExternalAccount.subject_token`:

* :mod:`Pyjo.GCP.Credentials.IdentityPool`, of a file or a URL,
* :mod:`Pyjo.GCP.Credentials.Pluggable`, of an executable.

With ``service_account_impersonation_url``, the token is the one of the
service account that the federated token impersonates, of
:mod:`Pyjo.GCP.Credentials.Impersonated`, and the federated token has the
scope of IAM, as google-auth has them.

The project is the one of the number of the project of the audience, or of
the workforce pool user project, of Cloud Resource Manager, which the
provider asks once, with its token, as google-auth does.

See also
--------

:mod:`Pyjo.GCP.Credentials.Provider`, :mod:`Pyjo.GCP.Credentials.File`,
https://google.aip.dev/auth/4117,
https://cloud.google.com/iam/docs/workload-identity-federation,
https://cloud.google.com/iam/docs/reference/sts/rest/v1/TopLevel/token.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.JSON

from Pyjo.Util import b64_encode, url_escape

from .. import Config, Credentials
from . import Impersonated, Provider

import re

from collections.abc import Mapping, Sequence
from typing import Any, Self, cast


TOKEN_URL = 'https://sts.{universe_domain}/v1/token'
"""The token endpoint of the Security Token Service of Google, of a universe domain."""

GRANT_TYPE = 'urn:ietf:params:oauth:grant-type:token-exchange'
"""The grant type of the token exchange of RFC 8693."""

REQUESTED_TOKEN_TYPE = 'urn:ietf:params:oauth:token-type:access_token'
"""The type of the token that the exchange gives, an access token."""

PROJECT_URL = 'https://cloudresourcemanager.googleapis.com/v1/projects/'
"""The URL of the projects of Cloud Resource Manager, of the project of a number, as google-auth has it."""

_WORKFORCE_POOL = re.compile(r'//iam\.googleapis\.com/locations/[^/]+/workforcePools/')


class Pyjo_GCP_Credentials_ExternalAccount(Provider.object):
    """
    :mod:`Pyjo.GCP.Credentials.ExternalAccount` inherits all attributes and
    methods from :mod:`Pyjo.GCP.Credentials.Provider` and implements the
    following new ones.
    """

    def __init__(
        self,
        *,
        audience: str,
        subject_token_type: str,
        token_url: str | None = None,
        service_account_impersonation_url: str | None = None,
        lifetime: int | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        scopes: Sequence[str] | None = None,
        quota_project: str | None = None,
        workforce_pool_user_project: str | None = None,
        universe_domain: str | None = None,
        project_url: str = PROJECT_URL,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.IdentityPool.new(audience=audience, subject_token_type=token_type,
                                                             file='/var/run/secrets/token')

        Construct a new provider of an external account, with the options of
        :mod:`Pyjo.GCP.Credentials.Provider`, or a :mod:`Pyjo.Exception` of
        a workforce pool user project of an audience that is not of a
        workforce pool.
        """
        super().__init__(**kwargs)

        self.audience = audience
        """::

            audience = provider.audience

        The resource name of the provider of the pool, as
        ``//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/oidc``.
        """

        self.subject_token_type = subject_token_type
        """::

            token_type = provider.subject_token_type

        The type of the subject token, as
        ``urn:ietf:params:oauth:token-type:jwt``.
        """

        self.universe_domain = universe_domain or Config.UNIVERSE_DOMAIN
        """::

            domain = provider.universe_domain

        The universe domain, ``googleapis.com`` by default.
        """

        self.token_url = token_url or TOKEN_URL.format(universe_domain=self.universe_domain)
        """::

            url = provider.token_url

        The token endpoint of the exchange, of the Security Token Service of
        :attr:`universe_domain` by default, ``https://sts.googleapis.com/v1/token``.
        """

        self.service_account_impersonation_url = service_account_impersonation_url
        """::

            url = provider.service_account_impersonation_url

        The URL of ``generateAccessToken`` of a service account that the
        federated token impersonates, or ``None``.
        """

        self.lifetime = lifetime
        """::

            seconds = provider.lifetime

        The number of seconds that the token of the impersonated service
        account is valid, or ``None``, for an hour.
        """

        self.client_id = client_id
        """::

            client_id = provider.client_id

        The ID of the OAuth client of a workforce pool, of the basic
        authentication of the exchange, or ``None``.
        """

        self.client_secret = client_secret
        """::

            secret = provider.client_secret

        The secret of the OAuth client, or ``None``.
        """

        self.scopes = list(scopes) if scopes else [Credentials.CLOUD_PLATFORM]
        """::

            scopes = provider.scopes

        The scopes of the token,
        ``https://www.googleapis.com/auth/cloud-platform`` by default.
        """

        self.quota_project = quota_project
        """::

            project = provider.quota_project

        The quota project of the credentials, or ``None``.
        """

        if workforce_pool_user_project and not self.is_workforce_pool():
            raise Pyjo.Exception.new(
                'Invalid credentials of an external account: a workforce_pool_user_project of an audience that is not'
                ' of a workforce pool'
            )

        self.workforce_pool_user_project = workforce_pool_user_project
        """::

            project = provider.workforce_pool_user_project

        The project of the quota of the exchange of a workforce pool without
        a :attr:`client_id`, or ``None``.
        """

        self.project_url = project_url
        """::

            url = provider.project_url

        The URL of the projects of Cloud Resource Manager,
        ``https://cloudresourcemanager.googleapis.com/v1/projects/``.
        """

        self.project: str | None = None
        """::

            project = provider.project

        The project of the number of the project, once the provider has
        asked for it, or ``None``.
        """

        self._project_asked = False
        self._impersonated: Impersonated.object | None = None

    @classmethod
    def from_info(cls, info: Mapping[str, Any], **kwargs: Any) -> Self:
        """::

            provider = IdentityPool.from_info(info)
            provider = IdentityPool.from_info(info, scopes=scopes, ua=ua)

        A new provider of the JSON object of a file of the type
        ``external_account``, with the fields of the file and the arguments
        over them, or a :mod:`Pyjo.Exception` of a file without ``audience``
        or ``subject_token_type``.
        """
        missing = [name for name in ('audience', 'subject_token_type') if not info.get(name)]
        if missing:
            raise Provider.invalid('an external account', missing)
        impersonation = info.get('service_account_impersonation')
        lifetime = (
            cast(Mapping[str, Any], impersonation).get('token_lifetime_seconds')
            if isinstance(impersonation, Mapping)
            else None
        )
        values: dict[str, Any] = {
            'audience': info['audience'],
            'subject_token_type': info['subject_token_type'],
            'token_url': info.get('token_url'),
            'service_account_impersonation_url': info.get('service_account_impersonation_url'),
            'lifetime': lifetime,
            'client_id': info.get('client_id'),
            'client_secret': info.get('client_secret'),
            'quota_project': info.get('quota_project_id'),
            'workforce_pool_user_project': info.get('workforce_pool_user_project'),
            'universe_domain': info.get('universe_domain'),
        }
        return cls(**{**values, **cls.options_of(info), **kwargs})

    @classmethod
    def options_of(cls, info: Mapping[str, Any]) -> dict[str, Any]:
        """::

            options = IdentityPool.options_of(info)

        The options of the provider of ``credential_source`` of the JSON
        object of a file, or a :mod:`Pyjo.Exception` of an invalid one. A
        subclass implements it; this one has none.
        """
        return {}

    def is_workforce_pool(self) -> bool:
        """::

            boolean = provider.is_workforce_pool()

        Whether :attr:`audience` is the one of a workforce pool, of Workforce
        Identity Federation of users.
        """
        return _WORKFORCE_POOL.match(self.audience) is not None

    def project_number(self) -> str | None:
        """::

            number = provider.project_number()

        The number of the project of :attr:`audience`, after ``projects/``,
        or ``None``.
        """
        components = self.audience.split('/')
        if 'projects' in components and (index := components.index('projects') + 1) < len(components):
            return components[index] or None
        return None

    async def exchange(self, scopes: Sequence[str] | None = None) -> Credentials.object:
        """::

            credentials = await provider.exchange()

        The federated token of the exchange of the subject token, with the
        scopes, :attr:`scopes` by default.
        """
        form: dict[str, str] = {
            'grant_type': GRANT_TYPE,
            'audience': self.audience,
            'scope': ' '.join(scopes or self.scopes),
            'requested_token_type': REQUESTED_TOKEN_TYPE,
            'subject_token': await self.subject_token(),
            'subject_token_type': self.subject_token_type,
        }
        if self.workforce_pool_user_project and not self.client_id:
            form['options'] = url_escape(Pyjo.JSON.to_json({'userProject': self.workforce_pool_user_project}))
        headers: dict[str, str] = {}
        if self.client_id:
            basic = b64_encode(f'{self.client_id}:{self.client_secret or ""}'.encode(), '')
            headers['Authorization'] = f'Basic {basic}'
        tx = await self.start(self.ua.build_tx('POST', self.token_url, headers, form=form))
        data = Provider.parse_token(tx, 'an external account')
        expires_in = data.get('expires_in')
        return Credentials.new(
            token=data['access_token'],
            expiration=Credentials.expiration_in(expires_in) if expires_in is not None else None,
            quota_project=self.quota_project,
            universe_domain=self.universe_domain,
            provider='external_account',
        )

    async def fetch(self) -> Credentials.object:
        """::

            credentials = await provider.fetch()

        The federated token, or the token of the impersonated service
        account, with the project of Cloud Resource Manager.
        """
        if self.service_account_impersonation_url is not None:
            credentials = await self.impersonated().steps()
            if credentials is None:
                raise Pyjo.Exception.new('Cannot get the token of an external account')
        else:
            credentials = await self.exchange()
        if not self._project_asked:
            self._project_asked = True
            self.project = await self._project(credentials)
        return credentials.copy(project=self.project, quota_project=self.quota_project)

    def impersonated(self) -> Impersonated.object:
        """::

            provider = provider.impersonated()

        The provider of the impersonated service account of
        :attr:`service_account_impersonation_url`, whose source is the
        federated token of the scope of IAM, made once, or a
        :mod:`Pyjo.Exception` of a URL without a service account.
        """
        if self._impersonated is None:
            url = self.service_account_impersonation_url or ''
            if (target := self.service_account()) is None:
                raise Pyjo.Exception.new(
                    f'Invalid credentials of an external account: no service account in {url!r}'
                )  # fmt: skip
            self._impersonated = Impersonated.new(
                source=_Federated(self, ua=self.ua, refresh=self.refresh),
                target_principal=target,
                scopes=self.scopes,
                lifetime=self.lifetime,
                quota_project=self.quota_project,
                url=url,
                ua=self.ua,
                refresh=self.refresh,
            )
        return self._impersonated

    def service_account(self) -> str | None:
        """::

            email = provider.service_account()

        The email of the service account of
        :attr:`service_account_impersonation_url`, between its last ``/`` and
        ``:generateAccessToken``, or ``None``.
        """
        url = self.service_account_impersonation_url or ''
        start, end = url.rfind('/'), url.find(':generateAccessToken')
        return url[start + 1 : end] if start != -1 and end != -1 and start < end else None

    async def subject_token(self) -> str:
        """::

            token = await provider.subject_token()

        The subject token of the other identity provider, a coroutine that
        awaits what it waits for, as :meth:`fetch` does. A subclass
        implements it; this one raises a :mod:`Pyjo.Exception`.
        """
        raise Pyjo.Exception.new('No subject token of an external account')

    async def _project(self, credentials: Credentials.object) -> str | None:
        number = self.project_number() or self.workforce_pool_user_project
        if not number:
            return None
        url = self.project_url + url_escape(number)
        tx = await self.start(self.ua.build_tx('GET', url, {'Authorization': f'Bearer {credentials.token}'}))
        try:
            data: Any = tx.res.json() if tx.res.code == 200 else None
        except ValueError:
            data = None
        project = cast(dict[str, Any], data).get('projectId') if isinstance(data, dict) else None
        return project if isinstance(project, str) and project else None


# The provider of the federated token of an external account, the source of its impersonated service account
class _Federated(Provider.object):
    def __init__(self, account: Pyjo_GCP_Credentials_ExternalAccount, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.account = account

    async def fetch(self) -> Credentials.object:
        return await self.account.exchange([Impersonated.IAM_SCOPE])


new = Pyjo_GCP_Credentials_ExternalAccount.new
object = Pyjo_GCP_Credentials_ExternalAccount
ExternalAccount = Pyjo_GCP_Credentials_ExternalAccount
