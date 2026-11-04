"""
Pyjo.GCP.Credentials.IdentityPool - Credentials of an identity pool of a file or a URL
======================================================================================
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

from . import ExternalAccount

from collections.abc import Mapping
from typing import Any, Literal, cast


type Format = Literal['text', 'json']


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
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.IdentityPool.new(audience=audience, subject_token_type=token_type,
                                                             file='/var/run/secrets/tokens/gcp-token')
            provider = Pyjo.GCP.Credentials.IdentityPool.new(audience=audience, subject_token_type=token_type,
                                                             url=url, headers={'Metadata': 'True'}, format='json',
                                                             subject_token_field_name='access_token')

        Construct a new :mod:`Pyjo.GCP.Credentials.IdentityPool` object, of
        a file or a URL, with the options of
        :mod:`Pyjo.GCP.Credentials.ExternalAccount`, or a
        :mod:`Pyjo.Exception` of none or both, or of a format of JSON without
        a field.
        """
        super().__init__(**kwargs)

        if file is None and url is None:
            raise _invalid('no file or url of the credential_source')
        if file is not None and url is not None:
            raise _invalid('both a file and a url of the credential_source')
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

    @classmethod
    def options_of(cls, info: Mapping[str, Any]) -> dict[str, Any]:
        """::

            options = IdentityPool.options_of(info)

        The options of ``file`` or ``url``, ``headers`` and ``format`` of
        ``credential_source`` of the JSON object of a file, or a
        :mod:`Pyjo.Exception` of a source of another kind, as an
        ``environment_id`` of AWS or a ``certificate`` of X.509.
        """
        source = info.get('credential_source')
        if not isinstance(source, Mapping):
            raise _invalid('no credential_source')
        source = cast(Mapping[str, Any], source)
        if 'environment_id' in source:
            raise _invalid(f'the environment_id of an identity pool {source["environment_id"]!r}')
        if 'certificate' in source:
            raise Pyjo.Exception.new('Unsupported credential_source of an external account: certificate of X.509')
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

    async def subject_token(self) -> str:
        """::

            token = await provider.subject_token()

        The subject token of :attr:`file` or :attr:`url`, or a
        :mod:`Pyjo.Exception` of a file that is not there, of a response
        that is not successful, or without the token.
        """
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


def _invalid(reason: str) -> Pyjo.Exception.object:
    return Pyjo.Exception.new(f'Invalid credentials of an external account: {reason}')


new = Pyjo_GCP_Credentials_IdentityPool.new
object = Pyjo_GCP_Credentials_IdentityPool
IdentityPool = Pyjo_GCP_Credentials_IdentityPool
