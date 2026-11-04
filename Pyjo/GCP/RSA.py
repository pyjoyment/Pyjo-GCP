"""
Pyjo.GCP.RSA - Signatures of RS256 of a key of RSA
==================================================
::

    from Pyjo.GCP.RSA import RSA

    key = RSA.from_pem(info['private_key'])
    signature = key.sign(b'header.payload')

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.RSA

    key = Pyjo.GCP.RSA.from_pem(pem, backend='python')
    token = key.jwt({'iss': 'reader@myproject.iam.gserviceaccount.com', 'iat': 1762257600}, key_id='3c5a...')
    print(key.verify(b'header.payload', signature))

:mod:`Pyjo.GCP.RSA` is a private key of RSA, as the key of a service account
of Google Cloud has it, which signs with SHA-256 and the padding of PKCS #1
v1.5, as RS256 of JSON Web Signature, of RFC 7518, has it, and makes the
JSON Web Tokens of :mod:`Pyjo.GCP.Credentials.ServiceAccount`.

The signature is the one of the package ``cryptography`` when it is
installed, as the extra ``cryptography`` of the distribution installs it: ::

    pip install 'Pyjo-GCP[cryptography]'

or of Python itself otherwise, whose signature is the same, as the padding of
PKCS #1 v1.5 is not random. That one is not constant-time: it is for a key
and a signature that are made on the machine that has the key, not for a
server that signs what anyone sends it.

See also
--------

:mod:`Pyjo.GCP.Credentials.ServiceAccount`, :rfc:`8017`, :rfc:`7518`,
:rfc:`7519`, https://cryptography.io/.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Exception
import Pyjo.JSON

from Pyjo.Util import b64_decode, b64url_encode, sha256_bytes

import functools
import importlib

from collections.abc import Mapping
from typing import Any, Literal, cast


# The object identifier of rsaEncryption of PKCS #1, as DER has it
_RSA_ENCRYPTION = bytes.fromhex('2a864886f70d010101')

# DigestInfo of SHA-256 of PKCS #1 v1.5, before the digest, RFC 8017, section 9.2
_SHA256_INFO = bytes.fromhex('3031300d060960864801650304020105000420')

type Backend = Literal['cryptography', 'python']


class Pyjo_GCP_RSA(Pyjo.Base.object):
    """
    :mod:`Pyjo.GCP.RSA` inherits all attributes and methods from
    :mod:`Pyjo.Base` and implements the following new ones.
    """

    def __init__(self, n: int, e: int, d: int, p: int, q: int, *, backend: Backend | None = None) -> None:
        """::

            key = Pyjo.GCP.RSA.new(n, e, d, p, q)
            key = Pyjo.GCP.RSA.new(n, e, d, p, q, backend='python')

        Construct a new :mod:`Pyjo.GCP.RSA` object of the modulus, the
        public and the private exponent and the primes of a key, with the
        backend of ``cryptography`` when it is installed, or of Python.
        """
        if p * q != n or not 1 < e < n or not 1 < d < n or e * d % ((p - 1) * (q - 1) // _gcd(p - 1, q - 1)) != 1:
            raise Pyjo.Exception.new('Invalid private key of RSA')

        self.n = n
        """::

            n = key.n

        The modulus of the key.
        """

        self.e = e
        """::

            e = key.e

        The public exponent of the key, as ``65537``.
        """

        self.d = d
        """::

            d = key.d

        The private exponent of the key.
        """

        self.p = p
        """::

            p = key.p

        The first prime of the key.
        """

        self.q = q
        """::

            q = key.q

        The second prime of the key.
        """

        crypto = _cryptography() if backend != 'python' else None
        if backend == 'cryptography' and crypto is None:
            raise Pyjo.Exception.new(
                "The backend cryptography of RSA is not installed: pip install 'Pyjo-GCP[cryptography]'"
            )

        self.backend: Backend = 'cryptography' if crypto is not None else 'python'
        """::

            name = key.backend

        The backend of the signatures, ``cryptography`` or ``python``.
        """

        self._key: Any = None
        if crypto is not None:
            public = crypto.rsa.RSAPublicNumbers(e, n)
            numbers = crypto.rsa.RSAPrivateNumbers(
                p, q, d, d % (p - 1), d % (q - 1), pow(q, -1, p), public
            )  # fmt: skip
            self._key = numbers.private_key()

    @classmethod
    def from_pem(cls, pem: str | bytes, *, backend: Backend | None = None) -> 'Pyjo_GCP_RSA':
        """::

            key = Pyjo.GCP.RSA.from_pem(pem)

        A new :mod:`Pyjo.GCP.RSA` object of a private key of RSA in PEM, of
        PKCS #8, ``BEGIN PRIVATE KEY``, as the key of a service account has
        it, or of PKCS #1, ``BEGIN RSA PRIVATE KEY``, without a password.
        """
        text = pem.decode() if isinstance(pem, bytes) else pem
        lines = [line.strip() for line in text.strip().splitlines()]
        if len(lines) < 3 or not lines[0].startswith('-----BEGIN ') or not lines[-1].startswith('-----END '):
            raise Pyjo.Exception.new('Invalid private key of RSA: not PEM')
        label = lines[0].removeprefix('-----BEGIN ').removesuffix('-----')
        try:
            der = b64_decode(''.join(lines[1:-1]))
            if label == 'PRIVATE KEY':
                numbers = _pkcs1(_pkcs8(der))
            elif label == 'RSA PRIVATE KEY':
                numbers = _pkcs1(der)
            else:
                raise ValueError(f'a PEM of {label}')
        except ValueError as e:
            raise Pyjo.Exception.new(f'Invalid private key of RSA: {e}') from None
        return cls(*numbers, backend=backend)

    def jwt(self, claims: Mapping[str, Any], *, key_id: str | None = None) -> str:
        """::

            token = key.jwt({'iss': email, 'aud': 'https://oauth2.googleapis.com/token', 'iat': iat, 'exp': exp})
            token = key.jwt(claims, key_id=info['private_key_id'])

        A JSON Web Token of RS256 of the claims, with the ID of the key in
        ``kid`` of its header, as google-auth makes it.
        """
        header: dict[str, str] = {'alg': 'RS256', 'typ': 'JWT'}
        if key_id:
            header['kid'] = key_id
        data = f'{_segment(header)}.{_segment(claims)}'
        return f'{data}.{b64url_encode(self.sign(data.encode()))}'

    def sign(self, data: bytes) -> bytes:
        """::

            signature = key.sign(b'header.payload')

        The signature of RS256 of data, of the length of the modulus.
        """
        if self._key is not None:
            crypto = cast(Any, _cryptography())
            return cast(bytes, self._key.sign(data, crypto.padding.PKCS1v15(), crypto.hashes.SHA256()))
        k = _length(self.n)
        m = int.from_bytes(_encode(sha256_bytes(data), k))
        p, q = self.p, self.q
        m1, m2 = pow(m, self.d % (p - 1), p), pow(m, self.d % (q - 1), q)
        s = m2 + (pow(q, -1, p) * (m1 - m2) % p) * q
        # A fault of the CRT would give away the key, so the signature is checked with the public key
        if pow(s, self.e, self.n) != m:
            raise Pyjo.Exception.new('Invalid signature of RSA')
        return s.to_bytes(k)

    def verify(self, data: bytes, signature: bytes) -> bool:
        """::

            boolean = key.verify(b'header.payload', signature)

        Whether a signature of RS256 of data is the one of the public key.
        """
        return verify(self.n, self.e, data, signature)


def verify(n: int, e: int, data: bytes, signature: bytes) -> bool:
    """::

        boolean = Pyjo.GCP.RSA.verify(n, e, b'header.payload', signature)

    Whether a signature of RS256 of data is the one of a public key, of its
    modulus and its exponent, in Python.
    """
    k = _length(n)
    if len(signature) != k or (s := int.from_bytes(signature)) >= n:
        return False
    return pow(s, e, n).to_bytes(k) == _encode(sha256_bytes(data), k)


# The modules of the package cryptography, which the distribution does not depend on, so that pyright takes them as Any
class _Crypto:
    def __init__(self) -> None:
        self.rsa: Any = importlib.import_module('cryptography.hazmat.primitives.asymmetric.rsa')
        self.padding: Any = importlib.import_module('cryptography.hazmat.primitives.asymmetric.padding')
        self.hashes: Any = importlib.import_module('cryptography.hazmat.primitives.hashes')


@functools.cache
def _cryptography() -> _Crypto | None:
    try:
        return _Crypto()
    except ImportError:
        return None


# EMSA-PKCS1-v1_5 of a digest of SHA-256, RFC 8017, section 9.2
def _encode(digest: bytes, k: int) -> bytes:
    t = _SHA256_INFO + digest
    if k < len(t) + 11:
        raise Pyjo.Exception.new('Invalid private key of RSA: too short')
    return b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def _length(n: int) -> int:
    return (n.bit_length() + 7) // 8


def _segment(value: Mapping[str, Any]) -> str:
    return b64url_encode(Pyjo.JSON.encode_json(dict(value)))


# A value of DER at a position: its tag, its content and the position after it
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


# PrivateKeyInfo of PKCS #8, RFC 5208, whose algorithm is rsaEncryption, with RSAPrivateKey of PKCS #1
def _pkcs8(der: bytes) -> bytes:
    items = _sequence(der)
    if len(items) < 3 or items[0][0] != 0x02 or items[0][1] not in (b'\x00', b'\x01'):
        raise ValueError('not a private key of PKCS #8')
    if items[1][0] != 0x30 or items[2][0] != 0x04:
        raise ValueError('not a private key of PKCS #8')
    algorithm = _elements(items[1][1])
    if not algorithm or algorithm[0] != (0x06, _RSA_ENCRYPTION):
        raise ValueError('not a key of RSA')
    return items[2][1]


# RSAPrivateKey of PKCS #1, RFC 8017, A.1.2, of two primes: the modulus, the exponents and the primes
def _pkcs1(der: bytes) -> tuple[int, int, int, int, int]:
    items = _sequence(der)
    if len(items) < 9 or items[0] != (0x02, b'\x00') or any(tag != 0x02 for tag, _ in items[1:9]):
        raise ValueError('not a private key of RSA of two primes')
    n, e, d, p, q = (int.from_bytes(value) for _, value in items[1:6])
    return n, e, d, p, q


def from_pem(pem: str | bytes, *, backend: Backend | None = None) -> Pyjo_GCP_RSA:
    """::

        key = Pyjo.GCP.RSA.from_pem(pem)

    Alias for :meth:`Pyjo_GCP_RSA.from_pem`.
    """
    return Pyjo_GCP_RSA.from_pem(pem, backend=backend)


new = Pyjo_GCP_RSA.new
object = Pyjo_GCP_RSA
RSA = Pyjo_GCP_RSA
