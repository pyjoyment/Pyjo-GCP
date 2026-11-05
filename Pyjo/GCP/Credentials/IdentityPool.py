"""
Pyjo.GCP.Credentials.IdentityPool - Credentials of an identity pool of a file, a URL or a certificate
=====================================================================================================
::

    from Pyjo.GCP.Credentials.IdentityPool import IdentityPool

    provider = IdentityPool(
        audience='//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/oidc',
        subject_token_type='urn:ietf:params:oauth:token-type:jwt',
        file='/var/run/secrets/tokens/gcp-token',
    )
    print(provider.credentials().token)

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Credentials.IdentityPool

    provider = Pyjo.GCP.Credentials.IdentityPool.IdentityPool.from_info(info)
    provider.credentials_p().then(lambda credentials: print(credentials.expiration)).wait()

:mod:`Pyjo.GCP.Credentials.IdentityPool` is the provider of the credentials
of an external account of Workload Identity Federation or Workforce Identity
Federation whose subject token is in a file, as the token of a service
account of Kubernetes, or the response of a URL, as the token of the managed
identity of Azure, of a file of the type ``external_account`` with
``credential_source`` of ``file`` or ``url``, as
``gcloud iam workload-identity-pools create-cred-config`` writes it: ::

    {
      "type": "external_account",
      "audience": "//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/azure",
      "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
      "token_url": "https://sts.googleapis.com/v1/token",
      "service_account_impersonation_url": "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/reader@myproject.iam.gserviceaccount.com:generateAccessToken",
      "credential_source": {
        "url": "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=api://pool",
        "headers": {"Metadata": "True"},
        "format": {"type": "json", "subject_token_field_name": "access_token"}
      }
    }

The subject token is the whole content of the file or of the response, as
``text`` of ``format``, or a field of its JSON object, as ``json``. The file
is read again for each token, as a token that the platform rotates.

The subject token of ``certificate`` is the certificate of X.509 of the
workload, of Workload Identity Federation with mTLS, with the certificates of
its trust chain, which the requests of the provider present with the private
key of the workload, to ``https://sts.mtls.googleapis.com/v1/token`` of the
file: ::

    {
      "type": "external_account",
      "audience": "//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/x509",
      "subject_token_type": "urn:ietf:params:oauth:token-type:mtls",
      "token_url": "https://sts.mtls.googleapis.com/v1/token",
      "credential_source": {
        "certificate": {
          "use_default_certificate_config": true,
          "trust_chain_path": "/etc/workload/chain.pem"
        }
      }
    }

The certificate and its key are the files of ``cert_configs.workload`` of the
configuration of ``certificate_config_location``, or of
``GOOGLE_API_CERTIFICATE_CONFIG``, of
``CLOUDSDK_CONTEXT_AWARE_CERTIFICATE_CONFIG_FILE_PATH``, or of
``~/.config/gcloud/certificate_config.json``, as gcloud and Cloud Run write
it: ::

    {
      "cert_configs": {
        "workload": {
          "cert_path": "/var/run/secrets/workload-spiffe-credentials/certificates.pem",
          "key_path": "/var/run/secrets/workload-spiffe-credentials/private_key.pem"
        }
      }
    }

The token of the certificate of an agent identity is bound to it, of
:mod:`Pyjo.GCP.X509`, for the calls of mTLS of :mod:`Pyjo.GCP.Client` with it.

See also
--------

:mod:`Pyjo.GCP.Credentials.ExternalAccount`,
:mod:`Pyjo.GCP.Credentials.File`, https://google.aip.dev/auth/4117.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.File
import Pyjo.JSON
import Pyjo.UserAgent

from Pyjo.Util import b64_decode, b64_encode

from .. import X509, Config
from . import ExternalAccount

import re

from collections.abc import Mapping
from typing import Any, Literal, cast


type Format = Literal['text', 'json']

MTLS = 'urn:ietf:params:oauth:token-type:mtls'
"""The type of the subject token of a certificate of X.509, of mTLS."""


_CERTIFICATE = re.compile(r'-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----', re.DOTALL)


class Pyjo_GCP_Credentials_IdentityPool(ExternalAccount.object):
    """
    :mod:`Pyjo.GCP.Credentials.IdentityPool` inherits all attributes and
    methods from :mod:`Pyjo.GCP.Credentials.ExternalAccount` and implements
    the following new ones.
    """

    def __init__(
        self,
        *,
        file: str | None = None,
        url: str | None = None,
        headers: Mapping[str, str] | None = None,
        format: Format = 'text',
        subject_token_field_name: str | None = None,
        certificate: bool = False,
        certificate_config_location: str | None = None,
        trust_chain_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.IdentityPool.new(audience=audience, subject_token_type=token_type,
                                                             file='/var/run/secrets/tokens/gcp-token')
            provider = Pyjo.GCP.Credentials.IdentityPool.new(audience=audience, subject_token_type=token_type,
                                                             url=url, headers={'Metadata': 'True'}, format='json',
                                                             subject_token_field_name='access_token')
            provider = Pyjo.GCP.Credentials.IdentityPool.new(audience=audience, subject_token_type=MTLS,
                                                             certificate=True, trust_chain_path='/etc/chain.pem')

        Construct a new :mod:`Pyjo.GCP.Credentials.IdentityPool` object, of
        a file, a URL or a certificate of X.509, with the options of
        :mod:`Pyjo.GCP.Credentials.ExternalAccount`, or a
        :mod:`Pyjo.Exception` of none or more than one of them, of a format of
        JSON without a field, or of a certificate without its configuration.
        """
        super().__init__(**kwargs)

        if (file is not None) + (url is not None) + certificate != 1:
            raise _invalid('one of a file, a url and a certificate of the credential_source')
        if format not in ('text', 'json'):
            raise _invalid(f'the format of the credential_source {format!r}')
        if format == 'json' and not subject_token_field_name:
            raise _invalid('no subject_token_field_name of the format json of the credential_source')

        self.file = file
        """::

            path = provider.file

        The file of the subject token, or ``None``.
        """

        self.url = url
        """::

            url = provider.url

        The URL of the subject token, or ``None``.
        """

        self.headers = dict(headers) if headers else {}
        """::

            headers = provider.headers

        The headers of the request of :attr:`url`.
        """

        self.format: Format = format
        """::

            format = provider.format

        The format of the subject token, ``text``, the whole content, or
        ``json``, a field of a JSON object.
        """

        self.subject_token_field_name = subject_token_field_name
        """::

            name = provider.subject_token_field_name

        The field of the subject token in the JSON object, or ``None``.
        """

        self.certificate = certificate
        """::

            boolean = provider.certificate

        Whether the subject token is the certificate of X.509 of the workload,
        of the configuration of :attr:`certificate_config_location`, which the
        requests of the provider present, of mTLS.
        """

        self.certificate_config_location = certificate_config_location
        """::

            path = provider.certificate_config_location

        The file of the configuration of the certificate, or ``None``, for
        the one of ``GOOGLE_API_CERTIFICATE_CONFIG``, of
        ``CLOUDSDK_CONTEXT_AWARE_CERTIFICATE_CONFIG_FILE_PATH``, or
        ``~/.config/gcloud/certificate_config.json``.
        """

        self.trust_chain_path = trust_chain_path
        """::

            path = provider.trust_chain_path

        The file of the certificates of the trust chain of the certificate,
        after it in the subject token, or ``None``.
        """

        # The user agent of mTLS, of the certificate and the key of the configuration, and the authority and the checks
        # of the one of the argument, which keeps no connections, as Metadata: nothing closes it, as a file makes a new
        # provider for each token, so a connection that it kept would be a socket that is not closed
        if certificate:
            cert, key = self.certificate_paths()
            self.ua = Pyjo.UserAgent.new(
                cert=cert, key=key, ca=self.ua.ca, insecure=self.ua.insecure, max_connections=0
            )  # fmt: skip

    @classmethod
    def options_of(cls, info: Mapping[str, Any]) -> dict[str, Any]:
        """::

            options = IdentityPool.options_of(info)

        The options of ``file`` or ``url``, ``headers`` and ``format``, or of
        ``certificate``, of ``credential_source`` of the JSON object of a
        file, or a :mod:`Pyjo.Exception` of a source of another kind, as an
        ``environment_id`` of AWS, or of a certificate with both or none of
        ``certificate_config_location`` and ``use_default_certificate_config``.
        """
        source = info.get('credential_source')
        if not isinstance(source, Mapping):
            raise _invalid('no credential_source')
        source = cast(Mapping[str, Any], source)
        if 'environment_id' in source:
            raise _invalid(f'the environment_id of an identity pool {source["environment_id"]!r}')
        if isinstance(certificate := source.get('certificate'), Mapping):
            certificate = cast(Mapping[str, Any], certificate)
            location, default = (
                certificate.get('certificate_config_location'),
                certificate.get('use_default_certificate_config'),
            )
            if bool(location) == bool(default):
                raise _invalid(
                    'one of certificate_config_location and use_default_certificate_config of the certificate'
                )
            return {
                'certificate': True,
                'certificate_config_location': location or None,
                'trust_chain_path': certificate.get('trust_chain_path') or None,
            }
        if 'executable' in source:
            raise Pyjo.Exception.new('Unsupported credential_source of an external account: executable')
        value = source.get('format')
        form: Mapping[str, Any] = cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}
        return {
            'file': source.get('file'),
            'url': source.get('url'),
            'headers': source.get('headers'),
            'format': form.get('type') or 'text',
            'subject_token_field_name': form.get('subject_token_field_name'),
        }

    def certificate_paths(self) -> tuple[str, str]:
        """::

            cert, key = provider.certificate_paths()

        The files of the certificate and of the private key of the workload,
        of :meth:`~Pyjo.GCP.Config.Pyjo_GCP_Config.workload_certificate` of
        the configuration of :attr:`certificate_config_location`, or of
        :meth:`~Pyjo.GCP.Config.Pyjo_GCP_Config.certificate_config`, or a
        :mod:`Pyjo.Exception` without them.
        """
        config = Config.new()
        location = self.certificate_config_location or config.certificate_config()
        if location is None or (paths := config.workload_certificate(location)) is None:
            missing = Pyjo.File.path(location or Config.CERTIFICATE_CONFIG).expanduser()
            raise _certificate(f'no configuration of the certificate {missing}')
        return paths

    def exchange_options(self) -> dict[str, str]:
        """::

            options = provider.exchange_options()

        The options of the exchange, with ``bindCertFingerprint`` of the
        fingerprint of the certificate of an agent identity, of
        :attr:`certificate`, which binds the token to it, as google-auth has
        it, unless ``GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES``
        is ``false``.
        """
        options = super().exchange_options()
        if self.certificate and X509.should_bind():
            cert, _ = self.certificate_paths()
            certificate = X509.from_pem(Pyjo.File.path(cert).slurp() or b'')
            if certificate.is_agent_identity():
                options['bindCertFingerprint'] = certificate.fingerprint()
        return options

    async def subject_token(self) -> str:
        """::

            token = await provider.subject_token()

        The subject token of :attr:`file` or :attr:`url`, or of the
        certificate, or a :mod:`Pyjo.Exception` of a file that is not there,
        of a response that is not successful, or without the token.
        """
        if self.certificate:
            return self.certificate_token()
        if self.file is not None:
            location = self.file
            path = Pyjo.File.path(location)
            if not path.is_file:
                raise Pyjo.Exception.new(f'Cannot read the subject token of an external account: {location}')
            content = path.slurp('UTF-8') or ''
        else:
            location = self.url or ''
            tx = await self.start(self.ua.build_tx('GET', location, self.headers))
            if tx.res.code != 200:
                raise Pyjo.Exception.new(
                    f'Cannot get the subject token of an external account: {location}:'
                    f' {tx.res.code} {tx.res.message or ""}'.strip()
                )
            content = tx.res.text
        token: Any = content
        if self.format == 'json':
            try:
                data: Any = Pyjo.JSON.from_json(content)
            except ValueError:
                data = None
            token = (
                cast(dict[str, Any], data).get(self.subject_token_field_name or '') if isinstance(data, dict) else None
            )
        if not isinstance(token, str) or not token:
            field = f' {self.subject_token_field_name}' if self.format == 'json' else ''
            raise Pyjo.Exception.new(f'No subject token{field} of an external account: {location}')
        return token

    def certificate_token(self) -> str:
        """::

            token = provider.certificate_token()

        The subject token of the certificate, a JSON array of the certificate
        and of the ones of :attr:`trust_chain_path` after it, each one in
        Base64 of DER, as google-auth makes it, or a :mod:`Pyjo.Exception` of
        a file of the certificate without one, or of a trust chain whose
        certificate is not first.
        """
        cert, _ = self.certificate_paths()
        leaf = _certificates(cert)
        if len(leaf) != 1:
            raise _certificate(f'not one certificate of PEM in {cert}')
        chain = _certificates(self.trust_chain_path) if self.trust_chain_path else []
        if chain and chain[0] == leaf[0]:
            chain = chain[1:]
        if leaf[0] in chain:
            raise _certificate(f'the certificate of the workload not first in the trust chain {self.trust_chain_path}')
        return '[' + ','.join(f'"{certificate}"' for certificate in leaf + chain) + ']'


# The certificates of PEM of a file, each one in Base64 of its DER, without its line breaks
def _certificates(path: str) -> list[str]:
    file = Pyjo.File.path(path)
    if not file.is_file:
        raise _certificate(f'no file of certificates {path}')
    try:
        return [
            b64_encode(b64_decode(re.sub(r'\s+', '', body)), '')
            for body in _CERTIFICATE.findall(file.slurp('UTF-8') or '')
        ]
    except ValueError as e:
        raise _certificate(f'invalid certificate of PEM in {path}: {e}') from None


def _certificate(reason: str) -> Pyjo.Exception.object:
    return Pyjo.Exception.new(f'Invalid certificate of an external account: {reason}')


def _invalid(reason: str) -> Pyjo.Exception.object:
    return Pyjo.Exception.new(f'Invalid credentials of an external account: {reason}')


new = Pyjo_GCP_Credentials_IdentityPool.new
object = Pyjo_GCP_Credentials_IdentityPool
IdentityPool = Pyjo_GCP_Credentials_IdentityPool
