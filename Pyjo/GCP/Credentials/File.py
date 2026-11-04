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

* ``authorized_user``, of :mod:`Pyjo.GCP.Credentials.AuthorizedUser`.

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

from .. import Config, Credentials
from . import AuthorizedUser, Provider

import os

from collections.abc import Mapping, Sequence
from typing import Any


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

        self.path = os.path.expanduser(path) if path else None
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
        if not (path := self.path) or self.optional and not os.path.isfile(path):
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

    def provider_of(self, info: Mapping[str, Any], path: str = 'a file') -> Provider.object:
        """::

            source = provider.provider_of(info)

        A new provider of the JSON object of a file of credentials, of its
        ``type``, with the user agent and the refresh of this one, or a
        :mod:`Pyjo.Exception` of a type that is not supported.
        """
        kind = info.get('type')
        if kind == 'authorized_user':
            return AuthorizedUser.AuthorizedUser.from_info(info, ua=self.ua, refresh=self.refresh)
        raise Pyjo.Exception.new(f'Unsupported type of the credentials of Google Cloud {path}: {kind!r}')


new = Pyjo_GCP_Credentials_File.new
object = Pyjo_GCP_Credentials_File
File = Pyjo_GCP_Credentials_File
