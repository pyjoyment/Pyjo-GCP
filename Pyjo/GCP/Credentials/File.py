"""
Pyjo.GCP.Credentials.File - Credentials of a file
=================================================
::

    from Pyjo.GCP.Credentials.File import File

    credentials = File(path='/etc/gcloud/key.json').credentials()

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Config
    import Pyjo.GCP.Credentials.File

    config = Pyjo.GCP.Config.new()

    # The file of gcloud auth application-default login, or None without it
    provider = Pyjo.GCP.Credentials.File.new(path=config.adc_file(), optional=True, config=config)
    provider.credentials_p().then(lambda credentials: print(credentials.project)).wait()

:mod:`Pyjo.GCP.Credentials.File` is the provider of the credentials of a
file of credentials of Google Cloud, as the one of
``GOOGLE_APPLICATION_CREDENTIALS`` or of
``gcloud auth application-default login``, of the provider of its ``type``:

* ``authorized_user``, of :mod:`Pyjo.GCP.Credentials.AuthorizedUser`,
* ``service_account``, of :mod:`Pyjo.GCP.Credentials.ServiceAccount`, with
  the scopes of the provider,
* ``impersonated_service_account``, of
  :mod:`Pyjo.GCP.Credentials.Impersonated`, with the scopes of the provider,
  and its source of the provider of the type of ``source_credentials``, with
  the scope of IAM,
* ``external_account``, of :mod:`Pyjo.GCP.Credentials.IdentityPool`, of a
  file or a URL, :mod:`Pyjo.GCP.Credentials.Pluggable`, of an executable,
  or :mod:`Pyjo.GCP.Credentials.AWS`, of AWS, with the scopes of the
  provider,
* ``external_account_authorized_user``, of
  :mod:`Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser`.

The quota project of ``GOOGLE_CLOUD_QUOTA_PROJECT`` comes over the one of
the file, and the file of ``gcloud auth application-default login``, which
has no project, has the one of the configuration of gcloud, ``core/project``,
as google-auth has them.

See also
--------

:mod:`Pyjo.GCP.Credentials.Provider`, :mod:`Pyjo.GCP.Credentials.Chain`,
:mod:`Pyjo.GCP.Config`, https://google.aip.dev/auth/4110.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.File

from .. import Config, Credentials
from . import (
    AWS,
    AuthorizedUser,
    ExternalAccountAuthorizedUser,
    IdentityPool,
    Impersonated,
    Pluggable,
    Provider,
    ServiceAccount,
)

from collections.abc import Mapping, Sequence
from typing import Any, cast


# The types of the source of an impersonated service account, as google-auth has them
_SOURCES = ('authorized_user', 'service_account', 'external_account_authorized_user')


class Pyjo_GCP_Credentials_File(Provider.object):
    """
    :mod:`Pyjo.GCP.Credentials.File` inherits all attributes and methods
    from :mod:`Pyjo.GCP.Credentials.Provider` and implements the following
    new ones.
    """

    def __init__(
        self,
        *,
        path: str | None = None,
        optional: bool = False,
        config: Config.object | None = None,
        scopes: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.File.new(path='/etc/gcloud/key.json')
            provider = Pyjo.GCP.Credentials.File.new(path=config.adc_file(), optional=True, config=config,
                                                     scopes=['https://www.googleapis.com/auth/devstorage.read_only'])

        Construct a new :mod:`Pyjo.GCP.Credentials.File` object, with the
        options of :mod:`Pyjo.GCP.Credentials.Provider`.
        """
        super().__init__(**kwargs)

        self.config = config or Config.new()
        """::

            config = provider.config

        The configuration of the quota project and of gcloud, a new
        :mod:`Pyjo.GCP.Config` object by default.
        """

        self.path = Pyjo.File.path(path).expanduser().to_str() if path else None
        """::

            path = provider.path

        The path of the file, or ``None``, which has no credentials, as an
        empty ``GOOGLE_APPLICATION_CREDENTIALS``.
        """

        self.optional = optional
        """::

            boolean = provider.optional

        Whether a file that does not exist has no credentials, as the one of
        ``gcloud auth application-default login``, rather than an error, as
        the one of ``GOOGLE_APPLICATION_CREDENTIALS``.
        """

        self.scopes = list(scopes) if scopes else [Credentials.CLOUD_PLATFORM]
        """::

            scopes = provider.scopes

        The scopes of the token of the credentials that take scopes,
        ``https://www.googleapis.com/auth/cloud-platform`` by default.
        """

    async def fetch(self) -> Credentials.object | None:
        """::

            credentials = await provider.fetch()

        The credentials of the provider of the file, or ``None`` without
        :attr:`path`, or without the file of an :attr:`optional` one.
        """
        if not (path := self.path) or self.optional and not Pyjo.File.path(path).is_file:
            return None
        credentials = await self.provider_of(self.config.credentials_info(path), path).steps()
        if credentials is None:
            return None
        changes: dict[str, Any] = {}
        if quota_project := self.config.quota_project():
            changes['quota_project'] = quota_project
        if credentials.project is None and self.is_gcloud() and (project := self.config.get('core/project')):
            changes['project'] = project
        return credentials.copy(**changes) if changes else credentials

    def is_gcloud(self) -> bool:
        """::

            boolean = provider.is_gcloud()

        Whether :attr:`path` is the file of
        ``gcloud auth application-default login`` of :attr:`config`, also of
        ``GOOGLE_APPLICATION_CREDENTIALS``, as google-auth compares them.
        """
        return self.path == self.config.adc_file()

    def provider_of(
        self, info: Mapping[str, Any], path: str = 'a file', *, scopes: Sequence[str] | None = None
    ) -> Provider.object:
        """::

            source = provider.provider_of(info)

        A new provider of the JSON object of a file of credentials, of its
        ``type``, with the user agent and the refresh of this one, and the
        scopes of the argument or of :attr:`scopes`, or a
        :mod:`Pyjo.Exception` of a type that is not supported.
        """
        kind = info.get('type')
        if kind == 'authorized_user':
            return AuthorizedUser.AuthorizedUser.from_info(info, ua=self.ua, refresh=self.refresh)
        if kind == 'service_account':
            return ServiceAccount.ServiceAccount.from_info(
                info, scopes=scopes or self.scopes, ua=self.ua, refresh=self.refresh
            )
        if kind == 'impersonated_service_account':
            value = info.get('source_credentials')
            source: Mapping[str, Any] = cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}
            if source.get('type') not in _SOURCES:
                raise Pyjo.Exception.new(
                    f'Unsupported type of the source credentials of Google Cloud {path}: {source.get("type")!r}'
                )
            return Impersonated.Impersonated.from_info(
                info,
                source=self.provider_of(source, path, scopes=[Impersonated.IAM_SCOPE]),
                scopes=scopes or self.scopes,
                ua=self.ua,
                refresh=self.refresh,
            )
        if kind == 'external_account':
            return self.external_account_of(info, path, scopes=scopes)
        if kind == 'external_account_authorized_user':
            return ExternalAccountAuthorizedUser.ExternalAccountAuthorizedUser.from_info(
                info, ua=self.ua, refresh=self.refresh
            )
        raise Pyjo.Exception.new(f'Unsupported type of the credentials of Google Cloud {path}: {kind!r}')

    def external_account_of(
        self, info: Mapping[str, Any], path: str = 'a file', *, scopes: Sequence[str] | None = None
    ) -> Provider.object:
        """::

            provider = provider.external_account_of(info)

        A new provider of the JSON object of a file of the type
        ``external_account``, of the kind of its source, as
        :meth:`provider_of`, or a :mod:`Pyjo.Exception` of an invalid one.
        """
        value = info.get('credential_source')
        source: Mapping[str, Any] = cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}
        options: dict[str, Any] = {'scopes': scopes or self.scopes, 'ua': self.ua, 'refresh': self.refresh}
        if info.get('subject_token_type') == AWS.SUBJECT_TOKEN_TYPE:
            return AWS.AWS.from_info(info, **options)
        if 'executable' in source:
            return Pluggable.Pluggable.from_info(info, **options)
        return IdentityPool.IdentityPool.from_info(info, **options)


new = Pyjo_GCP_Credentials_File.new
object = Pyjo_GCP_Credentials_File
File = Pyjo_GCP_Credentials_File
