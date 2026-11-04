import Pyjo.File
import Pyjo.GCP.RSA
import Pyjo.JSON

from Pyjo.Test import *
from Pyjo.Util import b64url_decode

import importlib
import importlib.util
import re
import shutil
import subprocess
import sys


# The key of RSA of the tests, of t/lib/Key.py
sys.path.insert(0, Pyjo.File.curfile().dirname().child('lib').to_str())
Key = importlib.import_module('Key')
N, E, D, P, Q, SIGNATURE = Key.N, Key.E, Key.D, Key.P, Key.Q, Key.SIGNATURE
pem, sequence, tlv, integer = Key.pem, Key.sequence, Key.tlv, Key.integer
PKCS1, PKCS8, PUBLIC = Key.PKCS1, Key.PKCS8, Key.PUBLIC

BACKENDS = ['python'] + (['cryptography'] if importlib.util.find_spec('cryptography') else [])


with subtest('Keys'):
    key = Pyjo.GCP.RSA.from_pem(pem('PRIVATE KEY', PKCS8), backend='python')
    is_ok((key.n, key.e, key.d, key.p, key.q), (N, E, D, P, Q), 'numbers of PKCS #8')
    is_ok(key.backend, 'python', 'backend of Python')
    key = Pyjo.GCP.RSA.from_pem(pem('RSA PRIVATE KEY', PKCS1).encode(), backend='python')
    is_ok(key.n, N, 'numbers of PKCS #1 of bytes')
    key = Pyjo.GCP.RSA.RSA.from_pem(pem('PRIVATE KEY', PKCS8).replace('\n', '\r\n'))
    is_ok(key.backend, BACKENDS[-1], 'backend of cryptography when it is installed')

    for name, text, error in (
        ('no PEM', 'MIIE', r'not PEM'),
        ('other label', pem('EC PRIVATE KEY', PKCS1), r'a PEM of EC PRIVATE KEY'),
        ('truncated', pem('PRIVATE KEY', PKCS8[:-10]), r'a truncated DER'),
        ('other algorithm', pem('PRIVATE KEY', sequence(integer(0), sequence(tlv(0x06, b'\x2a')), tlv(0x04, PKCS1))),
         r'not a key of RSA'),
        ('multi-prime', pem('RSA PRIVATE KEY', sequence(integer(1), *(integer(v) for v in (N, E, D, P, Q, 1, 1, 1)))),
         r'not a private key of RSA of two primes'),
        ('wrong prime', pem('RSA PRIVATE KEY', sequence(integer(0), *(integer(v) for v in (N, E, D, P, P, 1, 1, 1)))),
         r'$'),
    ):  # fmt: skip
        throws_ok(
            lambda text=text: Pyjo.GCP.RSA.from_pem(text), re.compile(rf'Invalid private key of RSA.*{error}'), name
        )

    if 'cryptography' in BACKENDS:
        skip('cryptography is installed', 1)
    else:
        throws_ok(
            lambda: Pyjo.GCP.RSA.new(N, E, D, P, Q, backend='cryptography'),
            re.compile(r'^The backend cryptography of RSA is not installed'),
            'backend that is not installed',
        )

with subtest('Signatures'):
    for backend in BACKENDS:
        key = Pyjo.GCP.RSA.new(N, E, D, P, Q, backend=backend)
        is_ok(key.sign(b'header.payload'), SIGNATURE, f'signature of RS256, {backend}')
        ok(key.verify(b'header.payload', SIGNATURE), f'verified, {backend}')
        ok(not key.verify(b'header.payload!', SIGNATURE), f'other data, {backend}')
        ok(not key.verify(b'header.payload', SIGNATURE[:-1]), f'short signature, {backend}')
        ok(not key.verify(b'header.payload', bytes(256)), f'other signature, {backend}')
    ok(Pyjo.GCP.RSA.verify(N, E, b'header.payload', SIGNATURE), 'verified with the public key')
    ok(not Pyjo.GCP.RSA.verify(N, E, b'header.payload', b'\xff' * 256), 'signature over the modulus')

with subtest('JSON Web Tokens'):
    key = Pyjo.GCP.RSA.new(N, E, D, P, Q)
    token = key.jwt({'iss': 'reader@myproject.iam.gserviceaccount.com', 'iat': 1762257600}, key_id='kid-1')
    header, claims, signature = token.split('.')
    is_ok(Pyjo.JSON.decode_json(b64url_decode(header)), {'alg': 'RS256', 'typ': 'JWT', 'kid': 'kid-1'}, 'header')
    is_ok(Pyjo.JSON.decode_json(b64url_decode(claims))['iat'], 1762257600, 'claims')
    ok(key.verify(f'{header}.{claims}'.encode(), b64url_decode(signature)), 'signature of the token')
    unlike_ok(token, re.compile(r'[=+/]'), 'base64url without padding')
    is_ok(Pyjo.JSON.decode_json(b64url_decode(key.jwt({}).split('.')[0])), {'alg': 'RS256', 'typ': 'JWT'}, 'no kid')

with subtest('Signatures verified by openssl'):
    if not shutil.which('openssl'):
        plan(skip_all='no openssl')
    tmp = Pyjo.File.tempdir()
    public = tmp.child('public.pem').spew(pem('PUBLIC KEY', PUBLIC))
    data = tmp.child('data').spew(b'header.payload')
    for backend in BACKENDS:
        signature = tmp.child(f'{backend}.sig').spew(
            Pyjo.GCP.RSA.new(N, E, D, P, Q, backend=backend).sign(b'header.payload')
        )
        done = subprocess.run(
            ['openssl', 'dgst', '-sha256', '-verify', str(public), '-signature', str(signature), str(data)],
            capture_output=True,
            check=False,
        )
        is_ok(done.returncode, 0, f'verified by openssl, {backend}')
    private = tmp.child('private.pem').spew(pem('PRIVATE KEY', PKCS8))
    done = subprocess.run(['openssl', 'pkey', '-in', str(private), '-noout'], capture_output=True, check=False)
    is_ok(done.returncode, 0, 'PEM of the test that openssl reads')

done_testing()
