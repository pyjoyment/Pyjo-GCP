"""
Pyjo.GCP.Credentials.Chain - Application Default Credentials
============================================================
::

    from Pyjo.GCP.Credentials.Chain import Chain

    credentials = Chain().credentials()
    print(credentials.project)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Config
    import Pyjo.GCP.Credentials.Chain
    import Pyjo.GCP.Credentials.File

    chain = Pyjo.GCP.Credentials.Chain.new(scopes=['https://www.googleapis.com/auth/devstorage.read_only'])
    chain.credentials_p().then(lambda credentials: print(credentials.provider)).wait()

    chain = Pyjo.GCP.Credentials.Chain.new(providers=[Pyjo.GCP.Credentials.File.new(path='/etc/gcloud/key.json')])

:mod:`Pyjo.GCP.Credentials.Chain` is the provider of the Application
Default Credentials, the credentials of the first of its providers that has
them, in the order of AIP-4110 by default:

#. the file of the ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable,
   of :mod:`Pyjo.GCP.Credentials.File`,
#. the file of ``gcloud auth application-default login``, of
   :mod:`Pyjo.GCP.Credentials.File`,
#. the metadata server of Compute Engine, GKE, Cloud Run and Cloud
   Functions, of :mod:`Pyjo.GCP.Credentials.Metadata`.

The project of the ``GOOGLE_CLOUD_PROJECT`` environment variable, or of
``GCLOUD_PROJECT``, comes over the one of the credentials, as google-auth has
it.

A provider that is not configured passes on to the next one, and the error
of one that is configured ends the chain, as google-auth does, so that a
broken file of ``GOOGLE_APPLICATION_CREDENTIALS`` is not hidden by other
credentials.

See also
--------

:mod:`Pyjo.GCP.Credentials.Provider`, :mod:`Pyjo.GCP.Credentials`,
:mod:`Pyjo.GCP.Config`, https://google.aip.dev/auth/4110.

Classes
-------
"""

from .. import Config, Credentials
from . import File, Metadata, Provider

from collections.abc import Sequence
from typing import Any


class Pyjo_GCP_Credentials_Chain(Provider.object):
    """
    :mod:`Pyjo.GCP.Credentials.Chain` inherits all attributes and methods
    from :mod:`Pyjo.GCP.Credentials.Provider` and implements the following
    new ones.
    """

    def __init__(
        self,
        *,
        providers: Sequence[Provider.object] | None = None,
        config: Config.object | None = None,
        scopes: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            chain = Pyjo.GCP.Credentials.Chain.new()
            chain = Pyjo.GCP.Credentials.Chain.new(scopes=['https://www.googleapis.com/auth/devstorage.read_only'])
            chain = Pyjo.GCP.Credentials.Chain.new(providers=[Pyjo.GCP.Credentials.File.new(path=path)])

        Construct a new :mod:`Pyjo.GCP.Credentials.Chain` object, with the
        options of :mod:`Pyjo.GCP.Credentials.Provider`, and the providers of
        the Application Default Credentials, with ``config`` and ``scopes``,
        by default.
        """
        super().__init__(**kwargs)

        self.config = config or Config.new()
        """::

            config = chain.config

        The configuration of the default providers and of the project, a new
        :mod:`Pyjo.GCP.Config` object by default.
        """

        self.scopes = list(scopes) if scopes else [Credentials.CLOUD_PLATFORM]
        """::

            scopes = chain.scopes

        The scopes of the token of the default providers that take scopes,
        ``https://www.googleapis.com/auth/cloud-platform`` by default.
        """

        self.providers: list[Provider.object] = list(providers) if providers is not None else self.default_providers()
        """::

            providers = chain.providers

        The providers, in their order.
        """

    def default_providers(self) -> list[Provider.object]:
        """::

            providers = chain.default_providers()

        New providers of the Application Default Credentials, with
        :attr:`config`, :attr:`scopes` and the user agent of the chain, in
        their order, but the metadata server, which has a user agent of its
        own, with a short timeout.
        """
        options: dict[str, Any] = {'config': self.config, 'scopes': self.scopes, 'ua': self.ua, 'refresh': self.refresh}
        return [
            File.new(path=self.config.credentials_file, **options),
            File.new(path=self.config.adc_file(), optional=True, **options),
            Metadata.new(scopes=self.scopes, refresh=self.refresh),
        ]

    async def fetch(self) -> Credentials.object | None:
        """::

            credentials = await chain.fetch()

        The credentials of the first provider that has them, with the project
        of the environment, or ``None``.
        """
        for provider in self.providers:
            if (credentials := await provider.steps()) is not None:
                if project := self.config.project():
                    return credentials.copy(project=project)
                return credentials
        return None


new = Pyjo_GCP_Credentials_Chain.new
object = Pyjo_GCP_Credentials_Chain
Chain = Pyjo_GCP_Credentials_Chain
