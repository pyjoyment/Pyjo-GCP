import Pyjo.File
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials.Chain
import Pyjo.GCP.Credentials.ExternalAccount
import Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser
import Pyjo.GCP.Credentials.File
import Pyjo.GCP.Credentials.IdentityPool
import Pyjo.JSON
import Pyjo.UserAgent

from Pyjo.GCP.Credentials.ExternalAccount import ExternalAccount
from Pyjo.GCP.Credentials.IdentityPool import IdentityPool
from Pyjo.Test import *
from Pyjo.Util import b64_decode, url_unescape
from Pyjoyment.Lite import *

import contextlib
import datetime
import os
import re


# The credentials of external accounts of Workload Identity Federation and Workforce Identity Federation, of a file
# and a URL, and of a user of a workforce pool, with the STS of Google, the IAM Service Account Credentials API and
# Cloud Resource Manager of an application of the test

tmp = Pyjo.File.tempdir()

app.log.level = 'fatal'

AUDIENCE = '//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/oidc'
WORKFORCE = '//iam.googleapis.com/locations/global/workforcePools/pool/providers/oidc'
JWT = 'urn:ietf:params:oauth:token-type:jwt'
TARGET = 'reader@myproject.iam.gserviceaccount.com'
CALLS = []


@post('/sts/token')
def sts(c):
    form = c.req.params.to_dict()
    authorization = c.req.headers.header('Authorization')
    CALLS.append(('sts', form, authorization))
    if form.get('grant_type') == 'refresh_token':
        if authorization != 'Basic Y2xpZW50OnNlY3JldA==':
            return c.render(json={'error': 'invalid_client'}, status=401)
        return c.render(json={'access_token': 'ya29.user', 'expires_in': 3600, 'refresh_token': 'rotated'})
    if form.get('subject_token') == 'invalid':
        return c.render(json={'error': 'invalid_grant', 'error_description': 'The audience does not match'},
                        status=400)  # fmt: skip
    c.render(json={'access_token': f'ya29.{form.get("subject_token")}', 'expires_in': '3599',
                   'issued_token_type': 'urn:ietf:params:oauth:token-type:access_token'})  # fmt: skip


@post('/iam/v1/projects/-/serviceAccounts/<*name>')
def iam(c):
    CALLS.append(('iam', c.param('name'), c.req.headers.header('Authorization'), c.req.json()))
    c.render(json={'accessToken': 'ya29.impersonated', 'expireTime': '2099-01-01T00:00:00Z'})


@get('/crm/<number>')
def crm(c):
    CALLS.append(('crm', c.param('number'), c.req.headers.header('Authorization')))
    if c.param('number') == 'denied':
        return c.render(json={'error': {'code': 403, 'message': 'Permission denied'}}, status=403)
    c.render(json={'projectNumber': c.param('number'), 'projectId': 'myproject'})


@get('/crm/v1/projects/<number>')
def crm_emulator(c):
    CALLS.append(('crm', c.param('number'), c.req.headers.header('Authorization')))
    c.render(json={'projectNumber': c.param('number'), 'projectId': 'emulated'})


@get('/subject')
def subject(c):
    CALLS.append(('subject', c.req.headers.header('Metadata')))
    if c.req.headers.header('Metadata') != 'True':
        return c.render(text='Forbidden', status=403)
    c.render(json={'access_token': 'url-token'})


ua = Pyjo.UserAgent.new()
ua.server.app = app

TOKEN = tmp.child('token').spew('file-token')
EMPTY = tmp.child('empty').spew('')


def info(**fields):
    return {
        'type': 'external_account',
        'audience': AUDIENCE,
        'subject_token_type': JWT,
        'token_url': '/sts/token',
        'credential_source': {'file': str(TOKEN)},
        **fields,
    }


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


def provider_of(fields, **kwargs):
    provider = Pyjo.GCP.Credentials.File.new(config=Pyjo.GCP.Config.new(), ua=ua, **kwargs).provider_of(fields)
    if hasattr(provider, 'project_url'):
        provider.project_url = '/crm/'
    return provider


class Supplier(ExternalAccount):
    async def subject_token(self):
        return 'supplied'


with environ():
    with subtest('Exchange of a file'):
        CALLS.clear()
        provider = provider_of(info(quota_project_id='quota'), scopes=['https://www.googleapis.com/auth/pubsub'])
        ok(isinstance(provider, IdentityPool), 'identity pool of a file')
        credentials = provider.credentials()
        is_ok(credentials.token, 'ya29.file-token', 'federated token')
        ok(3500 < credentials.expires_in() <= 3599, 'expiration of expires_in as a string')
        is_ok(
            (credentials.provider, credentials.project, credentials.quota_project, credentials.universe_domain),
            ('external_account', 'myproject', 'quota', 'googleapis.com'),
            'fields of the credentials',
        )
        _, form, authorization = CALLS[0]
        is_ok(
            form,
            {
                'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
                'audience': AUDIENCE,
                'scope': 'https://www.googleapis.com/auth/pubsub',
                'requested_token_type': 'urn:ietf:params:oauth:token-type:access_token',
                'subject_token': 'file-token',
                'subject_token_type': JWT,
            },
            'form of the exchange of RFC 8693',
        )
        is_ok(authorization, None, 'no client')
        is_ok(CALLS[1], ('crm', '123', 'Bearer ya29.file-token'), 'project of the number of the audience')

        CALLS.clear()
        provider.cached = None
        is_ok(provider.credentials().project, 'myproject', 'project again')
        is_ok([call[0] for call in CALLS], ['sts'], 'project once')

        result = wait(provider_of(info()).credentials_p())
        is_ok(result['value'].token, 'ya29.file-token', 'token, non-blocking')

        is_ok(Supplier.new(audience=AUDIENCE, subject_token_type=JWT, token_url='/sts/token', project_url='/crm/',
                           ua=ua).credentials().token, 'ya29.supplied', 'subject token of a subclass')  # fmt: skip
        is_ok(Supplier.new(audience=AUDIENCE, subject_token_type=JWT, universe_domain='example.goog').token_url,
              'https://sts.example.goog/v1/token', 'STS of the universe domain')  # fmt: skip

    with subtest('Exchange of a URL'):
        CALLS.clear()
        source = {'url': '/subject', 'headers': {'Metadata': 'True'},
                  'format': {'type': 'json', 'subject_token_field_name': 'access_token'}}  # fmt: skip
        is_ok(provider_of(info(credential_source=source)).credentials().token, 'ya29.url-token', 'token of JSON')
        is_ok(CALLS[0], ('subject', 'True'), 'headers of the URL')
        throws_ok(
            lambda: provider_of(info(credential_source={**source, 'headers': {}})).credentials(),
            re.compile(r'^Cannot get the subject token of an external account: /subject: 403 Forbidden'),
            'error of the URL',
        )
        throws_ok(
            lambda: provider_of(info(credential_source={
                **source, 'format': {'type': 'json', 'subject_token_field_name': 'id_token'}})).credentials(),
            re.compile(r'^No subject token id_token of an external account: /subject'),
            'JSON without the field',
        )  # fmt: skip

    with subtest('Workforce pools'):
        CALLS.clear()
        provider = provider_of(info(audience=WORKFORCE, workforce_pool_user_project='denied'))
        is_ok(provider.credentials().project, None, 'no project of a response that is not successful')
        options = Pyjo.JSON.from_json(url_unescape(CALLS[0][1]['options']))
        is_ok(options, {'userProject': 'denied'}, 'user project of the options')
        is_ok(CALLS[1][:2], ('crm', 'denied'), 'project of the user project')

        CALLS.clear()
        provider = provider_of(info(audience=WORKFORCE, workforce_pool_user_project='p', client_id='client',
                                    client_secret='secret'))  # fmt: skip
        provider.credentials()
        _, form, authorization = CALLS[0]
        ok('options' not in form, 'no options with a client')
        is_ok(b64_decode(authorization.removeprefix('Basic ')), b'client:secret', 'basic authentication')

        CALLS.clear()
        is_ok(provider_of(info(audience=WORKFORCE)).credentials().project, None, 'no project without a number')
        is_ok([call[0] for call in CALLS], ['sts'], 'no Cloud Resource Manager without a number')

    with subtest('Impersonation'):
        CALLS.clear()
        url = f'/iam/v1/projects/-/serviceAccounts/{TARGET}:generateAccessToken'
        provider = provider_of(info(service_account_impersonation_url=url, quota_project_id='quota',
                                    service_account_impersonation={'token_lifetime_seconds': 600}))  # fmt: skip
        credentials = provider.credentials()
        is_ok(
            (credentials.token, credentials.account, credentials.provider, credentials.project, credentials.quota_project),
            ('ya29.impersonated', TARGET, 'impersonated_service_account', 'myproject', 'quota'),
            'token of the service account',
        )  # fmt: skip
        is_ok([call[0] for call in CALLS], ['sts', 'iam', 'crm'], 'exchange, impersonation and project')
        is_ok(CALLS[0][1]['scope'], 'https://www.googleapis.com/auth/iam', 'scope of IAM of the exchange')
        is_ok(CALLS[1][1:], (f'{TARGET}:generateAccessToken', 'Bearer ya29.file-token',
                             {'scope': ['https://www.googleapis.com/auth/cloud-platform'], 'lifetime': '600s'}),
              'impersonation of the URL with the federated token')  # fmt: skip
        is_ok(CALLS[2][2], 'Bearer ya29.impersonated', 'project with the token of the service account')
        is_ok(provider.service_account(), TARGET, 'service account of the URL')

        CALLS.clear()
        provider.cached = None
        provider.credentials()
        is_ok(CALLS, [], 'token of the service account kept')
        provider.cached = provider.impersonated().cached = None
        provider.credentials()
        is_ok([call[0] for call in CALLS], ['iam'], 'federated token kept')

        throws_ok(
            lambda: provider_of(info(service_account_impersonation_url='/iam/')).credentials(),
            re.compile(r"^Invalid credentials of an external account: no service account in '/iam/'"),
            'URL without a service account',
        )

    with subtest('Emulators'):
        base = ua.server.url().to_str().rstrip('/')
        with environ(IAMCREDENTIALS_EMULATOR_HOST=f'{base}/iam', CLOUDRESOURCEMANAGER_EMULATOR_HOST=f'{base}/crm'):
            CALLS.clear()
            url = f'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{TARGET}:generateAccessToken'
            provider = provider_of(info(service_account_impersonation_url=url))
            provider.project_url = None
            credentials = provider.credentials()
            is_ok((credentials.token, credentials.project), ('ya29.impersonated', 'emulated'),
                  'token and project of the emulators')  # fmt: skip
            is_ok([call[0] for call in CALLS], ['sts', 'iam', 'crm'], 'exchange, impersonation and project')
            is_ok((CALLS[1][2], CALLS[2][2]), (None, None), 'emulators without a token')

            CALLS.clear()
            is_ok(provider_of(info()).credentials().project, 'myproject', 'URL of the projects over the emulator')
            is_ok(CALLS[-1], ('crm', '123', 'Bearer ya29.file-token'), 'URL of the projects with the token')

    with subtest('Errors'):
        throws_ok(
            lambda: provider_of(info(credential_source={'file': str(tmp.child('invalid').spew('invalid'))})).credentials(),
            re.compile(r'^Cannot get the token of an external account: invalid_grant: The audience does not match'),
            'error of the STS',
        )  # fmt: skip
        throws_ok(
            lambda: provider_of(info(credential_source={'file': str(tmp.child('missing'))})).credentials(),
            re.compile(r'^Cannot read the subject token of an external account: \S+missing'),
            'missing file',
        )
        throws_ok(
            lambda: provider_of(info(credential_source={'file': str(EMPTY)})).credentials(),
            re.compile(r'^No subject token of an external account: \S+empty'),
            'empty file',
        )
        invalid = [
            ({}, r"^Invalid credentials of an external account: no audience, subject_token_type$"),
            ({**info(), 'credential_source': None}, r'^Invalid credentials of an external account: no credential_source'),
            (info(credential_source={}), r'one of a file, a url and a certificate of the credential_source'),
            (info(credential_source={'file': 'a', 'url': 'b'}), r'one of a file, a url and a certificate of the credential_source'),
            (info(credential_source={'file': 'a', 'format': {'type': 'xml'}}), r"the format of the credential_source 'xml'"),
            (info(credential_source={'file': 'a', 'format': {'type': 'json'}}), r'no subject_token_field_name'),
            (info(credential_source={'environment_id': 'azure1', 'file': 'a'}), r"the environment_id of an identity pool 'azure1'"),
            (info(credential_source={'certificate': {}}), r'one of certificate_config_location and use_default_certificate_config'),
            (info(workforce_pool_user_project='p'), r'a workforce_pool_user_project of an audience that is not of a workforce pool'),
        ]  # fmt: skip
        for fields, error in invalid:
            throws_ok(
                lambda fields=fields: provider_of({'type': 'external_account', **fields}),
                re.compile(error),
                error.lstrip('^'),
            )

    with subtest('Users of a workforce pool'):
        user = {
            'type': 'external_account_authorized_user',
            'audience': WORKFORCE,
            'client_id': 'client',
            'client_secret': 'secret',
            'refresh_token': 'refresh',
            'token_url': '/sts/token',
            'quota_project_id': 'quota',
        }
        CALLS.clear()
        provider = provider_of(user)
        credentials = provider.credentials()
        is_ok(
            (credentials.token, credentials.provider, credentials.quota_project, credentials.project),
            ('ya29.user', 'external_account_authorized_user', 'quota', None),
            'token of the refresh token',
        )
        is_ok(CALLS[0][1], {'grant_type': 'refresh_token', 'refresh_token': 'refresh'}, 'refresh without scopes')
        is_ok(provider.refresh_token, 'rotated', 'refresh token rotated')

        CALLS.clear()
        provider = provider_of({**user, 'token': 'ya29.file', 'expiry': '2099-01-01T00:00:00.123456Z'})
        is_ok(provider.credentials().token, 'ya29.file', 'token of the file')
        is_ok(provider.cached.expiration, datetime.datetime(2099, 1, 1, 0, 0, 0, 123456, tzinfo=datetime.UTC),
              'expiry of the file')  # fmt: skip
        is_ok(CALLS, [], 'no refresh')
        provider = provider_of({**user, 'token': 'ya29.file', 'expiry': '2001-01-01T00:00:00Z'})
        is_ok(provider.credentials().token, 'ya29.user', 'expired token of the file refreshed')

        token_only = {
            'type': 'external_account_authorized_user',
            'token': 'ya29.file',
            'expiry': '2001-01-01T00:00:00Z',
        }
        throws_ok(
            lambda: provider_of(token_only).credentials(),
            re.compile(r'^Cannot get the token of an external account of a user: no refresh_token'),
            'expired token without a refresh',
        )
        throws_ok(
            lambda: provider_of({'type': 'external_account_authorized_user', 'client_id': 'client'}),
            re.compile(r'^Invalid credentials of an external account of a user: no refresh_token, token_url, client_secret$'),
            'file without a token or a refresh',
        )  # fmt: skip
        throws_ok(
            lambda: provider_of({**user, 'client_secret': 'other'}).credentials(),
            re.compile(r'^Cannot get the token of an external account of a user: invalid_client'),
            'error of the STS',
        )

with subtest('Chain'):
    path = tmp.child('workforce.json').spew(Pyjo.JSON.to_json(info(audience=WORKFORCE)))
    with environ(GOOGLE_APPLICATION_CREDENTIALS=str(path), GOOGLE_CLOUD_PROJECT='env-project',
                 GOOGLE_CLOUD_QUOTA_PROJECT='env-quota'):  # fmt: skip
        credentials = Pyjo.GCP.Credentials.Chain.new(ua=ua).credentials()
        is_ok(
            (credentials.token, credentials.project, credentials.quota_project),
            ('ya29.file-token', 'env-project', 'env-quota'),
            'external account of GOOGLE_APPLICATION_CREDENTIALS',
        )

done_testing()
