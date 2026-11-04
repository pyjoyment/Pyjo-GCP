import Pyjo.File
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials.AuthorizedUser
import Pyjo.GCP.Credentials.File
import Pyjo.GCP.Credentials.Impersonated
import Pyjo.GCP.Credentials.Provider
import Pyjo.JSON
import Pyjo.UserAgent

from Pyjo.GCP.Credentials.Impersonated import Impersonated
from Pyjo.Test import *
from Pyjo.Util import b64url_decode, b64url_encode
from Pyjoyment.Lite import *

import contextlib
import datetime
import importlib
import os
import re
import sys


# The credentials of an impersonated service account, with the IAM Service Account Credentials API and the token
# endpoint of an application of the test

sys.path.insert(0, Pyjo.File.curfile().dirname().child('lib').to_str())
Key = importlib.import_module('Key')

tmp = Pyjo.File.tempdir()

app.log.level = 'fatal'

TARGET = 'reader@myproject.iam.gserviceaccount.com'
CALLS = []


@post('/token')
def token(c):
    form = c.req.params.to_dict()
    CALLS.append(('token', form))
    if form.get('grant_type') == 'refresh_token':
        return c.render(json={'access_token': 'ya29.source', 'expires_in': 3599})
    if form.get('grant_type') == 'urn:ietf:params:oauth:grant-type:jwt-bearer':
        claims = Pyjo.JSON.decode_json(b64url_decode(form['assertion'].split('.')[1]))
        return c.render(json={'access_token': f'ya29.grant.{claims.get("sub", "key")}', 'expires_in': 3599})
    c.render(json={'error': 'unsupported_grant_type'}, status=400)


@post('/iam/v1/projects/-/serviceAccounts/<*name>')
def iam(c):
    account, method = c.param('name').split(':')
    CALLS.append((method, account, c.req.headers.header('Authorization'), c.req.headers.header('x-goog-user-project'),
                  c.req.json()))  # fmt: skip
    if account.startswith('denied'):
        return c.render(
            json={'error': {'code': 403, 'message': 'Permission denied', 'status': 'PERMISSION_DENIED'}}, status=403
        )
    if account.startswith('empty'):
        return c.render(json={})
    if method == 'signJwt':
        return c.render(
            json={'keyId': 'kid', 'signedJwt': f'header.{b64url_encode(c.req.json()["payload"].encode())}.signature'}
        )
    c.render(json={'accessToken': f'ya29.{account}', 'expireTime': '2099-01-01T00:00:00Z'})


ua = Pyjo.UserAgent.new()
ua.server.app = app


def source(**kwargs):
    return Pyjo.GCP.Credentials.AuthorizedUser.new(
        client_id='client', client_secret='secret', refresh_token='refresh', token_uri='/token', ua=ua, **kwargs
    )


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


class Nothing(Pyjo.GCP.Credentials.Provider.object):
    pass


with subtest('Token'):
    CALLS.clear()
    provider = Impersonated(
        source=source(quota_project='source-quota'),
        target_principal=TARGET,
        scopes=['https://www.googleapis.com/auth/devstorage.read_only'],
        delegates=['projects/-/serviceAccounts/broker@myproject.iam.gserviceaccount.com'],
        lifetime=600,
        quota_project='quota',
        endpoint='/iam',
        ua=ua,
    )
    credentials = provider.credentials()
    is_ok(credentials.token, f'ya29.{TARGET}', 'token of the service account')
    is_ok(credentials.expiration, datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC), 'expiration of expireTime')
    is_ok(
        (credentials.account, credentials.provider, credentials.quota_project, credentials.universe_domain),
        (TARGET, 'impersonated_service_account', 'quota', 'googleapis.com'),
        'fields of the credentials',
    )
    is_ok([call[0] for call in CALLS], ['token', 'generateAccessToken'], 'token of the source, then of the target')
    method, account, authorization, user_project, body = CALLS[1]
    is_ok((authorization, user_project), ('Bearer ya29.source', 'source-quota'), 'credentials of the source')
    is_ok(
        body,
        {
            'scope': ['https://www.googleapis.com/auth/devstorage.read_only'],
            'lifetime': '600s',
            'delegates': ['projects/-/serviceAccounts/broker@myproject.iam.gserviceaccount.com'],
        },
        'scopes, lifetime and delegates',
    )

    CALLS.clear()
    provider.cached = None
    is_ok(provider.credentials().token, f'ya29.{TARGET}', 'token again')
    is_ok([call[0] for call in CALLS], ['generateAccessToken'], 'source of its own cache')

    result = wait(Impersonated.new(source=source(), target_principal=TARGET, endpoint='/iam', ua=ua).credentials_p())
    is_ok(result['value'].token, f'ya29.{TARGET}', 'token, non-blocking')
    is_ok(CALLS[-1][4], {'scope': ['https://www.googleapis.com/auth/cloud-platform'], 'lifetime': '3600s'},
          'scope of cloud-platform and an hour by default, without delegates')  # fmt: skip

    url = f'/iam/v1/projects/-/serviceAccounts/{TARGET}:generateAccessToken'
    CALLS.clear()
    is_ok(Impersonated.new(source=source(), target_principal='other', url=url, ua=ua).credentials().token,
          f'ya29.{TARGET}', 'URL of generateAccessToken over the service account')  # fmt: skip

with subtest('Domain-wide delegation'):
    CALLS.clear()
    provider = Impersonated.new(source=source(), target_principal=TARGET, subject='admin@example.com',
                                endpoint='/iam', token_uri='/token', ua=ua)  # fmt: skip
    is_ok(provider.credentials().token, 'ya29.grant.admin@example.com', 'token of the grant')
    is_ok([call[0] for call in CALLS], ['token', 'signJwt', 'token'], 'signJwt, then the grant')
    claims = Pyjo.JSON.from_json(CALLS[1][4]['payload'])
    is_ok(
        {name: claims[name] for name in ('iss', 'sub', 'aud', 'scope')},
        {'iss': TARGET, 'sub': 'admin@example.com', 'aud': 'https://oauth2.googleapis.com/token',
         'scope': 'https://www.googleapis.com/auth/cloud-platform'},
        'claims of the JWT',
    )  # fmt: skip
    is_ok(claims['exp'] - claims['iat'], 3600, 'JWT of an hour')
    is_ok(CALLS[2][1]['grant_type'], 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'grant of RFC 7523')

    universe = source(universe_domain='example.goog')
    throws_ok(
        lambda: Impersonated.new(source=universe, target_principal=TARGET, subject='admin@example.com', endpoint='/iam',
                                 ua=ua).credentials(),
        re.compile(r'^Cannot get the token of the impersonated service account \S+: no domain-wide delegation in the'
                   r' universe domain example\.goog'),
        'no domain-wide delegation in another universe',
    )  # fmt: skip

with subtest('Errors'):
    throws_ok(
        lambda: Impersonated.new(source=source(), target_principal='denied@myproject.iam.gserviceaccount.com',
                                 endpoint='/iam', ua=ua).credentials(),
        re.compile(r'^Cannot get the token of the impersonated service account denied@\S+: 403 PERMISSION_DENIED:'
                   r' Permission denied'),
        'error of the API',
    )  # fmt: skip
    throws_ok(
        lambda: Impersonated.new(source=source(), target_principal='empty@myproject.iam.gserviceaccount.com',
                                 endpoint='/iam', ua=ua).credentials(),
        re.compile(r'^Cannot get the token of the impersonated service account empty@\S+: no accessToken or expireTime'),
        'response without a token',
    )  # fmt: skip
    throws_ok(
        lambda: Impersonated.new(source=Nothing.new(), target_principal=TARGET, endpoint='/iam', ua=ua).credentials(),
        re.compile(r'^Cannot get the token of the impersonated service account \S+: no credentials of the source'),
        'source without credentials',
    )

with subtest('Files'):
    with environ():
        provider_of = Pyjo.GCP.Credentials.File.new(config=Pyjo.GCP.Config.new(), ua=ua).provider_of
        user = {'type': 'authorized_user', 'client_id': 'client', 'client_secret': 'secret',
                'refresh_token': 'refresh', 'token_uri': '/token'}  # fmt: skip
        info = {
            'type': 'impersonated_service_account',
            'service_account_impersonation_url': f'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{TARGET}:generateAccessToken',
            'delegates': ['projects/-/serviceAccounts/broker@myproject.iam.gserviceaccount.com'],
            'quota_project_id': 'quota',
            'source_credentials': user,
        }  # fmt: skip
        provider = provider_of(info)
        is_ok(
            (provider.target_principal, provider.delegates, provider.quota_project, provider.url,
             type(provider.source).__name__),
            (TARGET, info['delegates'], 'quota', None, 'Pyjo_GCP_Credentials_AuthorizedUser'),
            'fields of the file, without its endpoint',
        )  # fmt: skip
        provider.endpoint = '/iam'
        is_ok(provider.credentials().token, f'ya29.{TARGET}', 'token of the file')

        key = {'type': 'service_account', 'client_email': 'source@myproject.iam.gserviceaccount.com',
               'private_key': Key.pem('PRIVATE KEY', Key.PKCS8), 'token_uri': '/token'}  # fmt: skip
        CALLS.clear()
        provider = provider_of({**info, 'source_credentials': key})
        provider.endpoint = '/iam'
        is_ok(provider.credentials().token, f'ya29.{TARGET}', 'token of a source of a key')
        claims = Pyjo.JSON.decode_json(b64url_decode(CALLS[0][1]['assertion'].split('.')[1]))
        is_ok(claims['scope'], 'https://www.googleapis.com/auth/iam', 'scope of IAM of the key')

        throws_ok(
            lambda: provider_of(
                {**info, 'service_account_impersonation_url': 'https://iamcredentials.googleapis.com/'}
            ),
            re.compile(r'^Invalid credentials of an impersonated service account: no service account in'),
            'URL without a service account',
        )
        throws_ok(
            lambda: provider_of({**info, 'source_credentials': {**info}}),
            re.compile(r"^Unsupported type of the source credentials of Google Cloud a file: 'impersonated_service_account'"),
            'impersonated service account as the source',
        )  # fmt: skip

done_testing()
