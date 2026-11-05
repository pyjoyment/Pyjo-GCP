"""
Pyjo.GCP.X509 - Certificates of X.509 of the workloads
======================================================
::

    from Pyjo.GCP.X509 import Certificate

    certificate = Certificate.from_pem(pem)
    print(certificate.fingerprint(), certificate.uris(), certificate.is_agent_identity())

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.X509

    fingerprint = Pyjo.GCP.X509.agent_fingerprint()

    # Or the steps that wait for the certificate, as a provider of credentials
    fingerprint = await Pyjo.GCP.X509.agent_fingerprint_steps()

:mod:`Pyjo.GCP.X509` is a certificate of X.509 of a workload, of the
configuration of the certificate of :mod:`Pyjo.GCP.Config`, as much of it as
the tokens of Google Cloud that are bound to it need: its DER, the
fingerprint of SHA-256 of its DER, and the URIs of its subjectAltName, of
which the SPIFFE ID of an agent identity of Google Cloud tells its
certificate, as ``_agent_identity_utils.py`` of google-auth has them, without
the package ``cryptography``.

A token of the metadata server and of an external account of a certificate
is bound to the certificate of an agent identity, with its fingerprint,
unless ``GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES`` is
``false``, so that the token is of the calls of mTLS with that certificate
only. The steps of :func:`agent_fingerprint_steps` wait for a certificate
that is not there yet, as of an agent that starts before its certificate is
written, for 30 seconds, as google-auth does.

See also
--------

:mod:`Pyjo.GCP.Config`, :mod:`Pyjo.GCP.Credentials.Metadata`,
:mod:`Pyjo.GCP.Credentials.IdentityPool`, :rfc:`5280`.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.File
import Pyjo.JSON
import Pyjo.Steps

from Pyjo.Util import b64_decode, b64_encode, getenv, sha256_bytes, url_escape

from . import Config

import re

from collections.abc import Sequence
from typing import Any, Self, cast


AGENT_TRUST_DOMAINS = (
    re.compile(r'^agents\.global\.org-\d+\.system\.id\.goog$'),
    re.compile(r'^agents\.global\.proj-\d+\.system\.id\.goog$'),
)
"""The trust domains of SPIFFE of the agent identities of Google Cloud."""

POLLING_INTERVALS: Sequence[float] = (0.1,) * 50 + (0.5,) * 50
"""The seconds of :func:`agent_fingerprint_steps` between the attempts to
find the certificate of an agent identity, 30 in all, as ``_POLLING_INTERVALS``
of google-auth has them."""

# The object identifier of subjectAltName of RFC 5280, as DER has it
_SUBJECT_ALT_NAME = bytes.fromhex('551d11')

_PEM = re.compile(r'-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----', re.DOTALL)


class Pyjo_GCP_X509_Certificate(Pyjo.Base.object):
    """
    :class:`Certificate` inherits all attributes and methods from
    :mod:`Pyjo.Base` and implements the following new ones.
    """

    def __init__(self, der: bytes) -> None:
        """::

            certificate = Pyjo.GCP.X509.Certificate.new(der)

        Construct a new certificate of its DER.
        """
        self.der = der
        """::

            der = certificate.der

        The DER of the certificate.
        """

    @classmethod
    def from_pem(cls, pem: str | bytes) -> Self:
        """::

            certificate = Certificate.from_pem(pem)

        The first certificate of PEM, or a :mod:`Pyjo.Exception` without one.
        """
        text = pem.decode() if isinstance(pem, bytes) else pem
        if (m := _PEM.search(text)) is None:
            raise Pyjo.Exception.new('Invalid certificate of X.509: not PEM')
        try:
            return cls(b64_decode(''.join(m[1].split())))
        except ValueError as e:
            raise Pyjo.Exception.new(f'Invalid certificate of X.509: {e}') from None

    def fingerprint(self) -> str:
        """::

            fingerprint = certificate.fingerprint()

        The fingerprint of SHA-256 of the DER, in Base64 without its padding,
        percent-encoded but its slashes, as google-auth sends it.
        """
        return url_escape(b64_encode(sha256_bytes(self.der), '').rstrip('='), r'^A-Za-z0-9\-._~/')

    def is_agent_identity(self) -> bool:
        """::

            boolean = certificate.is_agent_identity()

        Whether a URI of the certificate is the SPIFFE ID of an agent
        identity, of a trust domain of :data:`AGENT_TRUST_DOMAINS`.
        """
        for uri in self.uris():
            if (m := re.match(r'spiffe://([^/]+)', uri)) and any(p.match(m[1]) for p in AGENT_TRUST_DOMAINS):
                return True
        return False

    def uris(self) -> list[str]:
        """::

            uris = certificate.uris()

        The URIs of the subjectAltName of the certificate, or a
        :mod:`Pyjo.Exception` of an invalid DER.
        """
        try:
            certificate = _sequence(self.der)
            tbs = _elements(certificate[0][1]) if certificate and certificate[0][0] == 0x30 else []
            extensions = next((value for tag, value in tbs if tag == 0xA3), None)
            if extensions is None:
                return []
            for _, extension in _sequence(extensions):
                fields = _elements(extension)
                if fields and fields[0] == (0x06, _SUBJECT_ALT_NAME):
                    names = _sequence(fields[-1][1])
                    return [value.decode('ascii', 'replace') for tag, value in names if tag == 0x86]
        except ValueError as e:
            raise Pyjo.Exception.new(f'Invalid certificate of X.509: {e}') from None
        return []


def agent_fingerprint(config: Config.object | None = None) -> str | None:
    """::

        fingerprint = Pyjo.GCP.X509.agent_fingerprint()

    The fingerprint of the certificate of the agent identity of the workload,
    of the configuration of ``GOOGLE_API_CERTIFICATE_CONFIG``, or of the
    well-known one of Cloud Run, or ``None`` without them, of a certificate
    that is not of an agent identity, or of
    ``GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES=false``, as
    ``get_and_parse_agent_identity_certificate`` of google-auth has it, or a
    :mod:`Pyjo.Exception` of a configuration whose certificate is not there
    yet, at once, which :func:`agent_fingerprint_steps` waits for.
    """
    if not should_bind() or not getenv('GOOGLE_API_CERTIFICATE_CONFIG'):
        return None
    if (path := _agent_certificate_path()) is None:
        raise _no_agent_certificate()
    return _agent_fingerprint_of(path)


def agent_fingerprint_steps(
    config: Config.object | None = None, intervals: Sequence[float] | None = None
) -> Pyjo.Steps.object[str | None]:
    """::

        fingerprint = await Pyjo.GCP.X509.agent_fingerprint_steps()
        fingerprint = Pyjo.GCP.X509.agent_fingerprint_steps().run(ua)

    Same as :func:`agent_fingerprint`, but the :mod:`Pyjo.Steps` that wait
    for a certificate that is not there yet, with a sleep of each of the
    intervals, :data:`POLLING_INTERVALS` by default, as
    ``get_agent_identity_certificate_path`` of google-auth does, and raise
    the :mod:`Pyjo.Exception` after them.
    """
    return Pyjo.Steps.Steps(_agent_fingerprint_steps(POLLING_INTERVALS if intervals is None else intervals))


async def _agent_fingerprint_steps(intervals: Sequence[float]) -> str | None:
    if not should_bind() or not getenv('GOOGLE_API_CERTIFICATE_CONFIG'):
        return None
    for interval in intervals:
        if (path := _agent_certificate_path()) is not None:
            return _agent_fingerprint_of(path)
        await Pyjo.Steps.Sleep.new(interval)
    raise _no_agent_certificate(sum(intervals))


def should_bind() -> bool:
    """::

        boolean = Pyjo.GCP.X509.should_bind()

    Whether a token is bound to the certificate of an agent identity, unless
    ``GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES`` is ``false``.
    """
    return (getenv('GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES') or 'true').lower() != 'false'


# The certificate of the configuration of GOOGLE_API_CERTIFICATE_CONFIG, or the well-known one of Cloud Run, which is
# ready when it is not empty, as a file that is being written may be
def _agent_certificate_path() -> str | None:
    try:
        location = getenv('GOOGLE_API_CERTIFICATE_CONFIG') or ''
        data: Any = Pyjo.JSON.decode_json(Pyjo.File.path(location).slurp() or b'')
        configs = cast(dict[str, Any], data).get('cert_configs') if isinstance(data, dict) else None
        workload = cast(dict[str, Any], configs).get('workload') if isinstance(configs, dict) else None
        cert = cast(dict[str, Any], workload).get('cert_path') if isinstance(workload, dict) else None
        if isinstance(cert, str) and _is_ready(cert):
            return cert
    except (OSError, ValueError):
        pass
    return Config.CLOUD_RUN_CERT if _is_ready(Config.CLOUD_RUN_CERT) else None


def _agent_fingerprint_of(path: str) -> str | None:
    certificate = Certificate.from_pem(Pyjo.File.path(path).slurp() or b'')
    return certificate.fingerprint() if certificate.is_agent_identity() else None


def _no_agent_certificate(seconds: float | None = None) -> Pyjo.Exception.object:
    waited = f' in {seconds:g} seconds' if seconds else ''
    return Pyjo.Exception.new(
        f'No certificate of the agent identity of GOOGLE_API_CERTIFICATE_CONFIG{waited}: the binding of the token fails,'
        ' which GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES=false turns off'
    )


def _is_ready(path: str) -> bool:
    file = Pyjo.File.path(path)
    return file.is_file and file.stat().st_size > 0


# A value of DER at a position: its tag, its content and the position after it, as Pyjo.GCP.RSA reads them
def _tlv(der: bytes, pos: int) -> tuple[int, bytes, int]:
    if pos + 2 > len(der):
        raise ValueError('a truncated DER')
    tag, length = der[pos], der[pos + 1]
    pos += 2
    if length & 0x80:
        size = length & 0x7F
        if not 0 < size <= 4 or pos + size > len(der):
            raise ValueError('an invalid length of DER')
        length = int.from_bytes(der[pos : pos + size])
        pos += size
    if pos + length > len(der):
        raise ValueError('a truncated DER')
    return tag, der[pos : pos + length], pos + length


def _sequence(der: bytes) -> list[tuple[int, bytes]]:
    tag, content, end = _tlv(der, 0)
    if tag != 0x30 or end != len(der):
        raise ValueError('not a sequence of DER')
    return _elements(content)


def _elements(content: bytes) -> list[tuple[int, bytes]]:
    items: list[tuple[int, bytes]] = []
    pos = 0
    while pos < len(content):
        tag, value, pos = _tlv(content, pos)
        items.append((tag, value))
    return items


def from_pem(pem: str | bytes) -> Pyjo_GCP_X509_Certificate:
    """::

        certificate = Pyjo.GCP.X509.from_pem(pem)

    Alias for :meth:`Pyjo_GCP_X509_Certificate.from_pem`.
    """
    return Pyjo_GCP_X509_Certificate.from_pem(pem)


Certificate = Pyjo_GCP_X509_Certificate


new = Pyjo_GCP_X509_Certificate.new
object = Pyjo_GCP_X509_Certificate
