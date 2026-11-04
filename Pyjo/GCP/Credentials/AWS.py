"""
Pyjo.GCP.Credentials.AWS - Credentials of an external account of AWS
=====================================================================
::

    import Pyjo.GCP.Credentials.File

    # The file of gcloud iam workload-identity-pools create-cred-config --aws
    provider = Pyjo.GCP.Credentials.File.new(path='/etc/gcloud/aws.json')
    print(provider.credentials().token)

    # Or the provider itself

    from Pyjo.GCP.Credentials.AWS import AWS

    provider = AWS(
        audience='//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/aws',
        subject_token_type='urn:ietf:params:aws:token-type:aws4_request',
    )

:mod:`Pyjo.GCP.Credentials.AWS` is the provider of the credentials of an
external account of Workload Identity Federation of AWS, of a file of the
type ``external_account`` with the ``environment_id`` ``aws1`` of
``credential_source``, as
``gcloud iam workload-identity-pools create-cred-config --aws`` writes it: ::

    {
      "type": "external_account",
      "audience": "//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/aws",
      "subject_token_type": "urn:ietf:params:aws:token-type:aws4_request",
      "token_url": "https://sts.googleapis.com/v1/token",
      "credential_source": {
        "environment_id": "aws1",
        "region_url": "http://169.254.169.254/latest/meta-data/placement/availability-zone",
        "url": "http://169.254.169.254/latest/meta-data/iam/security-credentials",
        "regional_cred_verification_url": "https://sts.{region}.amazonaws.com?Action=GetCallerIdentity&Version=2011-06-15",
        "imdsv2_session_token_url": "http://169.254.169.254/latest/api/token"
      }
    }

The subject token is the request of ``GetCallerIdentity`` of the STS of AWS,
signed with Signature Version 4 and not sent, which the Security Token
Service of Google sends to AWS: the credentials of AWS are the ones of
``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY`` and ``AWS_SESSION_TOKEN``,
or of the role of the instance metadata of EC2, and the region is the one of
``AWS_REGION`` or ``AWS_DEFAULT_REGION``, or of the availability zone of the
instance metadata, as google-auth has them, without the profiles and the
other providers of the AWS CLI.

See also
--------

:mod:`Pyjo.GCP.Credentials.ExternalAccount`,
:mod:`Pyjo.GCP.Credentials.File`, https://google.aip.dev/auth/4117,
https://cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds,
https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv.html.

Classes
-------
"""

import Pyjo.Date
import Pyjo.Exception
import Pyjo.JSON
import Pyjo.URL

from Pyjo.Util import getenv, hmac_sha256_bytes, hmac_sha256_sum, sha256_sum, url_escape

from . import ExternalAccount

import re

from collections.abc import Mapping
from typing import Any, cast


SUBJECT_TOKEN_TYPE = 'urn:ietf:params:aws:token-type:aws4_request'
"""The type of the subject token of AWS, a signed request of AWS, of which the kind of a file is AWS."""

VERIFICATION_URL = 'https://sts.{region}.amazonaws.com?Action=GetCallerIdentity&Version=2011-06-15'
"""The URL of ``GetCallerIdentity`` of the STS of AWS of a region, of the request of the subject token."""

_IMDSV2_TTL = '300'
_UNRESERVED = r'^A-Za-z0-9\-._~'


class Pyjo_GCP_Credentials_AWS(ExternalAccount.object):
    """
    :mod:`Pyjo.GCP.Credentials.AWS` inherits all attributes and methods from
    :mod:`Pyjo.GCP.Credentials.ExternalAccount` and implements the following
    new ones.
    """

    def __init__(
        self,
        *,
        region_url: str | None = None,
        url: str | None = None,
        imdsv2_session_token_url: str | None = None,
        regional_cred_verification_url: str = VERIFICATION_URL,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.AWS.new(audience=audience, subject_token_type=token_type)

        Construct a new :mod:`Pyjo.GCP.Credentials.AWS` object, with the
        options of :mod:`Pyjo.GCP.Credentials.ExternalAccount`, of the
        credentials and the region of the environment without the URLs of
        the instance metadata.
        """
        super().__init__(**kwargs)

        self.region_url = region_url
        """::

            url = provider.region_url

        The URL of the availability zone of the instance metadata, of the
        region without ``AWS_REGION`` and ``AWS_DEFAULT_REGION``, or
        ``None``.
        """

        self.url = url
        """::

            url = provider.url

        The URL of the security credentials of the instance metadata, of the
        name of the role and of its credentials without
        ``AWS_ACCESS_KEY_ID`` and ``AWS_SECRET_ACCESS_KEY``, or ``None``.
        """

        self.imdsv2_session_token_url = imdsv2_session_token_url
        """::

            url = provider.imdsv2_session_token_url

        The URL of the session token of IMDSv2 of the requests of the
        instance metadata, or ``None``, for IMDSv1.
        """

        self.regional_cred_verification_url = regional_cred_verification_url
        """::

            url = provider.regional_cred_verification_url

        The URL of ``GetCallerIdentity`` of the subject token, with
        ``{region}`` of the region.
        """

        self.region: str | None = None
        """::

            region = provider.region

        The region of AWS, once the provider has found it, or ``None``.
        """

    @classmethod
    def options_of(cls, info: Mapping[str, Any]) -> dict[str, Any]:
        """::

            options = AWS.options_of(info)

        The options of the URLs of ``credential_source`` of the JSON object
        of a file, or a :mod:`Pyjo.Exception` of one without the
        ``environment_id`` ``aws1`` or ``regional_cred_verification_url``.
        """
        value = info.get('credential_source')
        source: Mapping[str, Any] = cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}
        environment = source.get('environment_id')
        match = re.fullmatch(r'aws(\d+)', environment) if isinstance(environment, str) else None
        if match is None or not source.get('regional_cred_verification_url'):
            raise _invalid('no environment_id or regional_cred_verification_url of AWS of the credential_source')
        if match[1] != '1':
            raise Pyjo.Exception.new(f'Unsupported credential_source of an external account: {environment}')
        return {
            'region_url': source.get('region_url'),
            'url': source.get('url'),
            'imdsv2_session_token_url': source.get('imdsv2_session_token_url'),
            'regional_cred_verification_url': source['regional_cred_verification_url'],
        }

    async def aws_credentials(self) -> tuple[str, str, str | None]:
        """::

            access_key_id, secret_access_key, session_token = await provider.aws_credentials()

        The credentials of AWS of the environment, or of the role of the
        instance metadata of :attr:`url`, or a :mod:`Pyjo.Exception` without
        them.
        """
        access_key_id, secret_access_key = getenv('AWS_ACCESS_KEY_ID'), getenv('AWS_SECRET_ACCESS_KEY')
        if access_key_id and secret_access_key:
            return access_key_id, secret_access_key, getenv('AWS_SESSION_TOKEN')
        if not self.url:
            raise Pyjo.Exception.new(
                'No credentials of AWS of an external account: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY,'
                ' or the url of the instance metadata'
            )
        headers = await self._imds_headers()
        role = await self._imds(self.url, headers, 'the role')
        body = await self._imds(f'{self.url}/{role}', headers, 'the credentials')
        try:
            data: Any = Pyjo.JSON.from_json(body)
        except ValueError:
            data = None
        fields = cast(dict[str, Any], data) if isinstance(data, dict) else {}
        access_key_id, secret_access_key = fields.get('AccessKeyId'), fields.get('SecretAccessKey')
        if not isinstance(access_key_id, str) or not isinstance(secret_access_key, str):
            raise Pyjo.Exception.new(f'No credentials of AWS of the instance metadata of the role {role}')
        token = fields.get('Token')
        return access_key_id, secret_access_key, token if isinstance(token, str) else None

    async def aws_region(self) -> str:
        """::

            region = await provider.aws_region()

        The region of AWS of the environment, or of the availability zone of
        the instance metadata of :attr:`region_url` without its letter, or a
        :mod:`Pyjo.Exception` without it.
        """
        if region := getenv('AWS_REGION') or getenv('AWS_DEFAULT_REGION'):
            return region
        if not self.region_url:
            raise Pyjo.Exception.new(
                'No region of AWS of an external account: AWS_REGION, AWS_DEFAULT_REGION, or the region_url of the'
                ' instance metadata'
            )
        zone = await self._imds(self.region_url, await self._imds_headers(), 'the region')
        return zone[:-1]

    async def subject_token(self) -> str:
        """::

            token = await provider.subject_token()

        The request of ``GetCallerIdentity`` of
        :attr:`regional_cred_verification_url`, signed with the credentials
        of AWS, with ``x-goog-cloud-target-resource`` of the audience, as the
        percent-encoded JSON object of its URL, its method and its headers.
        """
        if self.region is None:
            self.region = await self.aws_region()
        access_key_id, secret_access_key, session_token = await self.aws_credentials()
        url = self.regional_cred_verification_url.replace('{region}', self.region)
        headers = sign(
            url, 'POST', self.region, access_key_id, secret_access_key, session_token, Pyjo.Date.new().epoch or 0
        )
        headers['x-goog-cloud-target-resource'] = self.audience
        request = {
            'headers': [{'key': name, 'value': value} for name, value in headers.items()],
            'method': 'POST',
            'url': url,
        }
        return url_escape(Pyjo.JSON.to_json(request), _UNRESERVED + '/')

    async def _imds(self, url: str, headers: dict[str, str], name: str) -> str:
        tx = await self.start(self.ua.build_tx('GET', url, headers))
        if tx.res.code != 200:
            raise Pyjo.Exception.new(
                f'Cannot get {name} of AWS of the instance metadata: {tx.res.code} {tx.res.message or ""}'.strip()
            )
        return tx.res.text

    async def _imds_headers(self) -> dict[str, str]:
        if not self.imdsv2_session_token_url:
            return {}
        url = self.imdsv2_session_token_url
        tx = await self.start(self.ua.build_tx('PUT', url, {'X-aws-ec2-metadata-token-ttl-seconds': _IMDSV2_TTL}))
        if tx.res.code != 200:
            raise Pyjo.Exception.new(
                f'Cannot get the session token of AWS of the instance metadata: {tx.res.code} {tx.res.message or ""}'
                .strip()
            )  # fmt: skip
        return {'X-aws-ec2-metadata-token': tx.res.text}


def sign(
    url: str,
    method: str,
    region: str,
    access_key_id: str,
    secret_access_key: str,
    session_token: str | None = None,
    time: float = 0,
) -> dict[str, str]:
    """::

        headers = Pyjo.GCP.Credentials.AWS.sign(url, 'POST', 'eu-central-1', access_key_id, secret_access_key)

    The headers of a request of AWS with an empty body, signed with Signature
    Version 4, as ``RequestSigner`` of google-auth signs it: ``Authorization``,
    ``host``, ``x-amz-date`` and ``x-amz-security-token`` of a session token,
    of the service of the first label of the host, or a
    :mod:`Pyjo.Exception` of a URL that is not of HTTPS.
    """
    target = Pyjo.URL.new(url)
    host = target.host
    if not host or target.scheme != 'https':
        raise Pyjo.Exception.new(f'Invalid URL of AWS of an external account: {url}')
    date = Pyjo.Date.new(time)
    amz_date = f'{date:%Y%m%dT%H%M%SZ}'
    date_stamp = amz_date[:8]
    service = host.split('.')[0]
    signed: dict[str, str] = {'host': host, 'x-amz-date': amz_date}
    if session_token is not None:
        signed['x-amz-security-token'] = session_token
    names = sorted(signed)
    query = sorted((_escape(name), _escape(value)) for name, value in target.query.pairs)
    canonical = '\n'.join((
        method,
        _path(target.path.to_str()),
        '&'.join(f'{name}={value}' for name, value in query),
        ''.join(f'{name}:{signed[name]}\n' for name in names),
        ';'.join(names),
        sha256_sum(b''),
    ))  # fmt: skip
    scope = f'{date_stamp}/{region}/{service}/aws4_request'
    string_to_sign = '\n'.join(('AWS4-HMAC-SHA256', amz_date, scope, sha256_sum(canonical.encode())))
    key = ('AWS4' + secret_access_key).encode()
    for part in (date_stamp, region, service, 'aws4_request'):
        key = hmac_sha256_bytes(part.encode(), key)
    signature = hmac_sha256_sum(string_to_sign.encode(), key)
    headers = {
        'Authorization': f'AWS4-HMAC-SHA256 Credential={access_key_id}/{scope}, SignedHeaders={";".join(names)},'
        f' Signature={signature}',
        'host': host,
        'x-amz-date': amz_date,
    }
    if session_token is not None:
        headers['x-amz-security-token'] = session_token
    return headers


def _escape(value: str) -> str:
    return url_escape(value, _UNRESERVED)


# The path of the canonical request, normalized as posixpath.normpath of google-auth
def _path(path: str) -> str:
    segments: list[str] = []
    for segment in path.split('/'):
        if segment == '..':
            if segments:
                segments.pop()
        elif segment not in ('', '.'):
            segments.append(segment)
    return '/' + '/'.join(segments)


def _invalid(reason: str) -> Pyjo.Exception.object:
    return Pyjo.Exception.new(f'Invalid credentials of an external account: {reason}')


new = Pyjo_GCP_Credentials_AWS.new
object = Pyjo_GCP_Credentials_AWS
AWS = Pyjo_GCP_Credentials_AWS
