"""
Pyjo.GCP.Config - Configuration of gcloud and the environment of Google Cloud
=============================================================================
::

    from Pyjo.GCP.Config import Config

    config = Config()
    print(config.config_dir, config.active_configuration(), config.get('core/project'))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Config

    config = Pyjo.GCP.Config.new(configuration='dev')
    print(config.project() or config.get('core/project'))
    print(config.endpoint_url('storage'))

:mod:`Pyjo.GCP.Config` reads what the client libraries of Google and the
gcloud CLI read of the environment and of the configuration directory of
gcloud, as the Application Default Credentials find them: the file of the
credentials of ``GOOGLE_APPLICATION_CREDENTIALS``, the one of
``gcloud auth application-default login``, the properties of the
configurations of gcloud, the project, the quota project, the universe
domain and the endpoint of a service.

The configuration directory is the one of the ``CLOUDSDK_CONFIG``
environment variable, or ``~/.config/gcloud``, or ``%APPDATA%\\gcloud`` on
Windows. A configuration of gcloud is the file
``configurations/config_<name>`` of the directory, whose sections have the
properties, as ``project`` of ``[core]``: ::

    [core]
    project = myproject
    account = me@example.com

    [auth]
    impersonate_service_account = reader@myproject.iam.gserviceaccount.com

The files are read when a method needs them, once, and a file that does not
exist has no properties.

See also
--------

:mod:`Pyjo.GCP`, https://google.aip.dev/auth/4110,
https://google.aip.dev/auth/4113,
https://cloud.google.com/sdk/docs/configurations.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.File
import Pyjo.JSON

from Pyjo.Util import getenv

import configparser
import os
import re

from typing import Any, cast


ADC_FILE = 'application_default_credentials.json'
"""The name of the file of the credentials of ``gcloud auth application-default login`` in the configuration
directory."""

UNIVERSE_DOMAIN = 'googleapis.com'
"""The universe domain of Google Cloud, of the endpoints of its APIs."""


class Pyjo_GCP_Config(Pyjo.Base.object):
    """
    :mod:`Pyjo.GCP.Config` inherits all attributes and methods from
    :mod:`Pyjo.Base` and implements the following new ones.
    """

    def __init__(
        self,
        *,
        config_dir: str | None = None,
        configuration: str | None = None,
        credentials_file: str | None = None,
    ) -> None:
        """::

            config = Pyjo.GCP.Config.new()
            config = Pyjo.GCP.Config.new(config_dir='/etc/gcloud', configuration='dev')

        Construct a new :mod:`Pyjo.GCP.Config` object.
        """
        self.config_dir = (
            Pyjo.File.path(config_dir or getenv('CLOUDSDK_CONFIG') or _default_dir()).expanduser().to_str()
        )
        """::

            path = config.config_dir
            config.config_dir = '/etc/gcloud'

        The path of the configuration directory of gcloud, defaults to the
        value of the ``CLOUDSDK_CONFIG`` environment variable,
        ``~/.config/gcloud``, or ``%APPDATA%\\gcloud`` on Windows.
        """

        self.configuration = configuration or getenv('CLOUDSDK_ACTIVE_CONFIG_NAME') or None
        """::

            name = config.configuration
            config.configuration = 'dev'

        The name of the configuration of gcloud, defaults to the value of the
        ``CLOUDSDK_ACTIVE_CONFIG_NAME`` environment variable, or ``None`` for
        the active one of the directory, see :meth:`active_configuration`.
        """

        file = credentials_file or getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self.credentials_file = Pyjo.File.path(file).expanduser().to_str() if file else None
        """::

            path = config.credentials_file
            config.credentials_file = '/etc/gcloud/key.json'

        The path of the file of the credentials, defaults to the value of the
        ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable, or ``None``.
        """

        self._active: str | None = None
        self._properties: dict[str, dict[str, dict[str, str]]] = {}

    def active_configuration(self) -> str:
        """::

            name = config.active_configuration()

        The name of the configuration of gcloud, :attr:`configuration`, the
        one of the file ``active_config`` of the directory, which
        ``gcloud config configurations activate`` writes, or ``default``.
        """
        if self.configuration:
            return self.configuration
        if self._active is None:
            self._active = (_slurp(Pyjo.File.path(self.config_dir, 'active_config')) or '').strip()
        return self._active or 'default'

    def adc_file(self) -> str:
        """::

            path = config.adc_file()

        The path of the file of the credentials of
        ``gcloud auth application-default login`` in :attr:`config_dir`,
        which may not exist.
        """
        return Pyjo.File.path(self.config_dir, ADC_FILE).to_str()

    def credentials_info(self, path: str) -> dict[str, Any]:
        """::

            info = config.credentials_info(config.adc_file())

        The JSON object of a file of credentials, which raises a
        :mod:`Pyjo.Exception` of a file that does not exist, is not JSON, or
        is not an object.
        """
        try:
            data = Pyjo.File.path(path).slurp()
        except OSError as e:
            raise Pyjo.Exception.new(f'Cannot read the credentials of Google Cloud: {e}') from e
        try:
            info: Any = Pyjo.JSON.decode_json(data)
        except ValueError as e:
            raise Pyjo.Exception.new(f'Cannot parse the credentials of Google Cloud {path}: {e}') from e
        if not isinstance(info, dict):
            raise Pyjo.Exception.new(f'Cannot parse the credentials of Google Cloud {path}: not an object')
        return cast(dict[str, Any], info)

    def emulator_host(self, service: str) -> str | None:
        """::

            url = config.emulator_host('storage')

        The URL of the emulator of a service, of the value of the
        ``<SERVICE>_EMULATOR_HOST`` environment variable, as
        ``STORAGE_EMULATOR_HOST``, with ``http://`` before a host without a
        scheme, as ``localhost:4443``, or ``None``.
        """
        if not (host := getenv(f'{_key(service).upper()}_EMULATOR_HOST')):
            return None
        return host if '://' in host else f'http://{host}'

    def endpoint_url(self, service: str) -> str:
        """::

            url = config.endpoint_url('storage')

        The URL of the endpoint of a service, of :meth:`emulator_host`, or
        the one of the service in :meth:`universe_domain`, as
        ``https://storage.googleapis.com``.
        """
        return self.emulator_host(service) or f'https://{service}.{self.universe_domain()}'

    def get(self, name: str, configuration: str | None = None) -> str | None:
        """::

            project = config.get('core/project')
            account = config.get('account', 'dev')

        The value of a property of gcloud, of its section and name, as
        ``core/project``, or of its name in ``core``, as ``project``: the
        value of the ``CLOUDSDK_<SECTION>_<NAME>`` environment variable, as
        ``CLOUDSDK_CORE_PROJECT``, or of the property of a configuration,
        :meth:`active_configuration` by default, or ``None``.
        """
        section, _, key = name.rpartition('/')
        section = section or 'core'
        if value := getenv(f'CLOUDSDK_{_key(section).upper()}_{_key(key).upper()}'):
            return value
        return self.properties(configuration).get(section, {}).get(key) or None

    def project(self) -> str | None:
        """::

            project = config.project()

        The project of the environment, of the value of the
        ``GOOGLE_CLOUD_PROJECT`` environment variable, or of
        ``GCLOUD_PROJECT``, or ``None``, which comes over the project of the
        credentials.
        """
        return getenv('GOOGLE_CLOUD_PROJECT') or getenv('GCLOUD_PROJECT') or None

    def properties(self, configuration: str | None = None) -> dict[str, dict[str, str]]:
        """::

            properties = config.properties()
            properties = config.properties('dev')

        The sections of the properties of a configuration of gcloud,
        :meth:`active_configuration` by default, without the environment, or
        an empty :class:`dict`.
        """
        name = configuration or self.active_configuration()
        if name not in self._properties:
            self._properties[name] = _parse(Pyjo.File.path(self.config_dir, 'configurations', f'config_{name}'))
        return {section: dict(values) for section, values in self._properties[name].items()}

    def quota_project(self) -> str | None:
        """::

            project = config.quota_project()

        The quota project of the environment, of the value of the
        ``GOOGLE_CLOUD_QUOTA_PROJECT`` environment variable, or ``None``,
        which comes over the one of the credentials.
        """
        return getenv('GOOGLE_CLOUD_QUOTA_PROJECT') or None

    def universe_domain(self) -> str:
        """::

            domain = config.universe_domain()

        The universe domain of the endpoints, of the value of the
        ``GOOGLE_CLOUD_UNIVERSE_DOMAIN`` environment variable, or
        ``googleapis.com``.
        """
        return getenv('GOOGLE_CLOUD_UNIVERSE_DOMAIN') or UNIVERSE_DOMAIN


# The directory of gcloud of _cloud_sdk.get_config_path of google-auth
def _default_dir() -> str:
    if os.name != 'nt':
        return Pyjo.File.path('~', '.config', 'gcloud').to_str()
    if appdata := getenv('APPDATA'):
        return Pyjo.File.path(appdata, 'gcloud').to_str()
    return Pyjo.File.path(getenv('SystemDrive') or 'C:', '\\', 'gcloud').to_str()


def _key(name: str) -> str:
    return re.sub(r'[\s-]+', '_', name.strip())


# The sections of a file of properties of gcloud, or none of a file that does not exist
def _parse(file: Pyjo.File.object) -> dict[str, dict[str, str]]:
    if (text := _slurp(file)) is None:
        return {}
    parser = configparser.RawConfigParser(strict=False, default_section='\0')
    try:
        parser.read_string(text, file.to_str())
    except configparser.Error as e:
        raise Pyjo.Exception.new(f'Cannot parse the configuration of gcloud {file}: {e.message}') from e
    return {section: dict(parser.items(section)) for section in parser.sections()}


# The characters of a file, or None of a file that does not exist or is not of UTF-8
def _slurp(file: Pyjo.File.object) -> str | None:
    try:
        return file.slurp('UTF-8')
    except (FileNotFoundError, NotADirectoryError):
        return None


new = Pyjo_GCP_Config.new
object = Pyjo_GCP_Config
Config = Pyjo_GCP_Config
