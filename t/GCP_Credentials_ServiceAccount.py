import Pyjo.File
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials.Chain
import Pyjo.GCP.Credentials.File
import Pyjo.GCP.Credentials.ServiceAccount
import Pyjo.GCP.RSA
import Pyjo.JSON
import Pyjo.UserAgent

from Pyjo.GCP.Credentials.ServiceAccount import ServiceAccount
from Pyjo.Test import *
from Pyjo.Util import b64url_decode
from Pyjoyment.Lite import *

import contextlib
import datetime
import importlib
import os
import re
import sys


# The credentials of the key of a service account, of the grant of a JWT, which the token endpoint of an application of
# the test checks with the public key, and of a self-signed JWT

sys.path.insert(0, Pyjo.File.curfile().dirname().child('lib').to_str())
Key = importlib.import_module('Key')

tmp = Pyjo.File.tempdir()

app.log.level = 'fatal'

EMAIL = 'reader@myproject.iam.gserviceaccount.com'
GRANTS = []


def decode(token):
    header, claims, signature = token.split('.')
    if not Pyjo.GCP.RSA.verify(Key.N, Key.E, f'{header}.{claims}'.encode(), b64url_decode(signature)):
        return None, None
    return Pyjo.JSON.decode_json(b64url_decode(header)), Pyjo.JSON.decode_json(b64url_decode(claims))


@post('/token')
def token(c):
    if c.param('grant_type') != 'urn:ietf:params:oauth:grant-type:jwt-bearer':
        return c.render(json={'error': 'unsupported_grant_type'}, status=400)
    header, claims = decode(c.param('assertion'))
    if claims is None:
        return c.render(json={'error': 'invalid_grant', 'error_description': 'Invalid JWT Signature.'}, status=400)
    GRANTS.append((header, claims))
    if claims['iss'] != EMAIL:
        return c.render(json={'error': 'invalid_grant', 'error_description': 'Invalid grant: account not found'},
                        status=400)  # fmt: skip
    c.render(json={'access_token': 'ya29.service', 'expires_in': 3599, 'token_type': 'Bearer'})


ua = Pyjo.UserAgent.new()
ua.server.app = app

PEM = Key.pem('PRIVATE KEY', Key.PKCS8)


def info(**fields):
    return {
        'type': 'service_account',
        'project_id': 'myproject',
        'private_key_id': 'kid-1',
        'private_key': PEM,
        'client_email': EMAIL,
        'client_id': '1234567890',
        'token_uri': '/token',
        'universe_domain': 'googleapis.com',
        **fields,
    }


KEY = tmp.child('key.json').spew(Pyjo.JSON.to_json(info()))


@contextlib.contextmanager
def environ(**values):
    saved = dict(os.environ)
    try:
        for name in list(os.environ):
            if name.startswith(('GOOGLE_', 'GCLOUD_', 'CLOUDSDK_', 'GCE_')):
                del os.environ[name]
        os.environ.update({'CLOUDSDK_CONFIG': str(tmp.child('gcloud')), 'NO_GCE_CHECK': 'True', **values})
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


def wait(promise):
    result = {}
    promise.then(
        lambda *values: result.update(value=values[0] if len(values) == 1 else values),
        lambda reason: result.update(error=reason),
    ).wait()
    return result


with subtest('Grant'):
    GRANTS.clear()
    provider = ServiceAccount.from_info(info(), ua=ua)
    credentials = provider.credentials()
    is_ok(credentials.token, 'ya29.service', 'access token')
    ok(3500 < credentials.expires_in() <= 3599, 'expiration')
    is_ok(
        (credentials.project, credentials.account, credentials.universe_domain, credentials.provider),
        ('myproject', EMAIL, 'googleapis.com', 'service_account'),
        'fields of the key',
    )
    header, claims = GRANTS[0]
    is_ok(header, {'alg': 'RS256', 'typ': 'JWT', 'kid': 'kid-1'}, 'header of the JWT')
    is_ok(
        {name: claims[name] for name in ('iss', 'aud', 'scope')},
        {'iss': EMAIL, 'aud': 'https://oauth2.googleapis.com/token', 'scope': 'https://www.googleapis.com/auth/cloud-platform'},
        'claims of the grant, the audience of Google for another token endpoint',
    )  # fmt: skip
    is_ok(claims['exp'] - claims['iat'], 3600, 'JWT of an hour')
    ok('sub' not in claims, 'no subject')

    scopes = ['https://www.googleapis.com/auth/devstorage.read_only', 'https://www.googleapis.com/auth/pubsub']
    result = wait(ServiceAccount.from_info(info(), scopes=scopes, subject='admin@example.com', ua=ua).credentials_p())
    is_ok(result['value'].token, 'ya29.service', 'access token, non-blocking')
    header, claims = GRANTS[-1]
    is_ok(claims['scope'], ' '.join(scopes), 'scopes')
    is_ok(claims['sub'], 'admin@example.com', 'subject of the domain-wide delegation')

    throws_ok(
        lambda: ServiceAccount.from_info(info(client_email='other@myproject.iam.gserviceaccount.com'), ua=ua).credentials(),
        re.compile(r'^Cannot get the token of the service account other@\S+: invalid_grant: Invalid grant'),
        'error of the token endpoint',
    )  # fmt: skip
    is_ok(Pyjo.GCP.Credentials.ServiceAccount.new(client_email=EMAIL, private_key=PEM).token_uri,
          'https://oauth2.googleapis.com/token', 'token endpoint of Google')  # fmt: skip

with subtest('Self-signed JWT'):
    GRANTS.clear()
    provider = ServiceAccount.from_info(info(), self_signed=True, ua=ua)
    credentials = provider.credentials()
    is_ok(GRANTS, [], 'no request')
    header, claims = decode(credentials.token)
    is_ok(header['kid'], 'kid-1', 'JWT of the key')
    is_ok(
        {name: claims[name] for name in ('iss', 'sub', 'scope')},
        {'iss': EMAIL, 'sub': EMAIL, 'scope': 'https://www.googleapis.com/auth/cloud-platform'},
        'claims of AIP-4111',
    )
    ok('aud' not in claims, 'scope without an audience')
    is_ok(credentials.expiration, datetime.datetime.fromtimestamp(claims['exp'], datetime.UTC), 'expiration of the JWT')

    provider = ServiceAccount.from_info(info(universe_domain='example.goog'), ua=ua)
    ok(provider.self_signed, 'self-signed JWT of another universe')
    is_ok(provider.credentials().universe_domain, 'example.goog', 'universe of the key')
    is_ok(GRANTS, [], 'no request of another universe')
    provider = ServiceAccount.from_info(info(), self_signed=True, subject='admin@example.com', ua=ua)
    is_ok(provider.credentials().token, 'ya29.service', 'grant of a subject')

with subtest('Invalid keys'):
    throws_ok(
        lambda: ServiceAccount.from_info({'type': 'service_account', 'client_email': EMAIL}),
        re.compile(r'^Invalid credentials of a service account: no private_key, token_uri$'),
        'file without its fields',
    )
    throws_ok(
        lambda: ServiceAccount.from_info(info(private_key='-----BEGIN PRIVATE KEY-----\nMIIE\n-----END PRIVATE KEY-----\n')),
        re.compile(r'^Invalid private key of RSA: '),
        'invalid key',
    )  # fmt: skip

with subtest('File and chain'):
    with environ():
        config = Pyjo.GCP.Config.new()
        scopes = ['https://www.googleapis.com/auth/devstorage.read_only']
        GRANTS.clear()
        credentials = Pyjo.GCP.Credentials.File.new(path=str(KEY), config=config, scopes=scopes, ua=ua).credentials()
        is_ok((credentials.provider, credentials.project), ('service_account', 'myproject'), 'file of the key')
        is_ok(GRANTS[0][1]['scope'], scopes[0], 'scopes of the file')

    with environ(GOOGLE_APPLICATION_CREDENTIALS=str(KEY)):
        credentials = Pyjo.GCP.Credentials.Chain.new(ua=ua).credentials()
        is_ok((credentials.account, credentials.project), (EMAIL, 'myproject'), 'key of GOOGLE_APPLICATION_CREDENTIALS')

    with environ(GOOGLE_APPLICATION_CREDENTIALS=str(KEY), GOOGLE_CLOUD_PROJECT='env-project',
                 GOOGLE_CLOUD_QUOTA_PROJECT='quota'):  # fmt: skip
        credentials = Pyjo.GCP.Credentials.Chain.new(ua=ua).credentials()
        is_ok((credentials.project, credentials.quota_project), ('env-project', 'quota'), 'projects of the environment')

done_testing()
