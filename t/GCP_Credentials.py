import Pyjo.Exception
import Pyjo.File
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials
import Pyjo.GCP.Credentials.AuthorizedUser
import Pyjo.GCP.Credentials.Chain
import Pyjo.GCP.Credentials.File
import Pyjo.GCP.Credentials.Provider
import Pyjo.JSON
import Pyjo.Promise
import Pyjo.UserAgent

from Pyjo.Test import *
from Pyjoyment.Lite import *

import contextlib
import datetime
import os
import re


# Credentials of Google Cloud and their providers, with the token endpoint of OAuth 2.0 of an application of the test,
# and files and an environment of their own, without the metadata server

tmp = Pyjo.File.tempdir()

NOW = datetime.datetime.now(datetime.UTC)

app.log.level = 'fatal'

REQUESTS = []


@post('/token')
def token(c):
    form = c.req.params.to_dict()
    REQUESTS.append(form)
    if form.get('grant_type') != 'refresh_token' or (form.get('client_id'), form.get('client_secret')) != (
        'client',
        'secret',
    ):
        return c.render(json={'error': 'invalid_client', 'error_description': 'Unauthorized'}, status=401)
    refresh_token = form.get('refresh_token')
    if refresh_token == 'revoked':
        return c.render(
            json={'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'}, status=400
        )
    if refresh_token == 'broken':
        return c.render(text='Bad Gateway', status=502)
    data = {'access_token': f'ya29.{refresh_token}', 'expires_in': 3599, 'token_type': 'Bearer'}
    if refresh_token == 'rotate':
        data['refresh_token'] = 'rotated'
    c.render(json=data)


ua = Pyjo.UserAgent.new()
ua.server.app = app


def user(refresh_token='refresh', **fields):
    info = {
        'type': 'authorized_user',
        'client_id': 'client',
        'client_secret': 'secret',
        'refresh_token': refresh_token,
        'token_uri': '/token',
        **fields,
    }
    return Pyjo.JSON.to_json(info)


GCLOUD = tmp.child('gcloud')
GCLOUD.child('configurations').make_path()
GCLOUD.child('configurations', 'config_default').spew('[core]\nproject = gcloud-project\n')
ADC = GCLOUD.child('application_default_credentials.json')
KEY = tmp.child('user.json').spew(user('explicit', quota_project_id='file-quota', account='me@example.com'))


# The variables of Google Cloud and gcloud of the environment of the test only, without those of the machine
@contextlib.contextmanager
def environ(**values):
    saved = dict(os.environ)
    try:
        for name in list(os.environ):
            if name.startswith(('GOOGLE_', 'GCLOUD_', 'CLOUDSDK_', 'GCE_')):
                del os.environ[name]
        os.environ.update({'CLOUDSDK_CONFIG': str(GCLOUD), 'NO_GCE_CHECK': 'True', **values})
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


with subtest('Credentials'):
    credentials = Pyjo.GCP.Credentials.new(token='ya29.secret', account='me@example.com')
    is_ok(credentials.expires_in(), None, 'no expiration')
    is_ok(repr(credentials), "<Credentials account='me@example.com' provider=None>", 'no token in repr')
    credentials.expiration = NOW + datetime.timedelta(minutes=10)
    is_ok(credentials.expires_in(NOW), 600.0, 'expires in seconds')

    copy = credentials.copy(project='myproject')
    is_ok((copy.token, copy.project, copy.expiration), ('ya29.secret', 'myproject', credentials.expiration), 'copy')
    is_ok(credentials.project, None, 'original of the copy')

    expiration = Pyjo.GCP.Credentials.expiration_in('3600')
    ok(3590 < (expiration - datetime.datetime.now(datetime.UTC)).total_seconds() <= 3600, 'expiration in seconds')
    throws_ok(
        lambda: Pyjo.GCP.Credentials.expiration_in('soon'),
        re.compile(r"^Invalid expiration of a token of Google Cloud: 'soon'"),
        'invalid expiration in seconds',
    )
    is_ok(
        Pyjo.GCP.Credentials.parse_time('2026-11-04T12:00:00Z'),
        datetime.datetime(2026, 11, 4, 12, tzinfo=datetime.UTC),
        'time of RFC 3339',
    )
    throws_ok(
        lambda: Pyjo.GCP.Credentials.parse_time('tomorrow'),
        re.compile(r"^Invalid expiration of a token of Google Cloud: 'tomorrow'"),
        'invalid time',
    )

with subtest('Provider'):

    class Counted(Pyjo.GCP.Credentials.Provider.object):
        def __init__(self, minutes, **kwargs):
            super().__init__(**kwargs)
            self.minutes = minutes
            self.count = 0

        async def fetch(self):
            tx = await self.start(self.ua.build_tx('POST', '/token', form={
                'grant_type': 'refresh_token', 'client_id': 'client', 'client_secret': 'secret',
                'refresh_token': 'counted',
            }))  # fmt: skip
            self.count += 1
            data = Pyjo.GCP.Credentials.Provider.parse_token(tx, 'the test')
            expiration = None if self.minutes is None else NOW + datetime.timedelta(minutes=self.minutes)
            return Pyjo.GCP.Credentials.new(token=data['access_token'], expiration=expiration)

    provider = Counted(60, ua=ua)
    is_ok(provider.refresh, 225, 'refresh of google-auth')
    is_ok(provider.credentials().token, 'ya29.counted', 'credentials')
    provider.credentials()
    is_ok(provider.count, 1, 'credentials cached')
    ok(provider.is_fresh(), 'fresh')

    provider = Counted(3, ua=ua)
    provider.credentials()
    provider.credentials()
    is_ok(provider.count, 2, 'credentials about to expire got again')

    provider = Counted(None, ua=ua)
    provider.credentials()
    provider.credentials()
    is_ok(provider.count, 1, 'credentials without expiration cached')

    provider = Counted(60, ua=ua)
    first, second = provider.credentials_p(), provider.credentials_p()
    ok(first is second, 'same promise while pending')
    wait(Pyjo.Promise.all(first, second))
    is_ok(provider.count, 1, 'credentials got once')
    ok(provider.credentials_p() is not first, 'cached credentials of a new promise')

    is_ok(Pyjo.GCP.Credentials.Provider.new().credentials(), None, 'no credentials of the base class')

with subtest('Tokens'):

    class Response(Pyjo.GCP.Credentials.Provider.object):
        def __init__(self, code, body, **kwargs):
            super().__init__(**kwargs)
            self.code, self.body = code, body

        async def fetch(self):
            tx = self.ua.build_tx('GET', '/')
            tx.res.code = self.code
            tx.res.body = self.body
            Pyjo.GCP.Credentials.Provider.parse_token(tx, 'the test')

    throws_ok(
        lambda: Response(400, b'{"error": "invalid_grant", "error_description": "Bad"}').credentials(),
        re.compile(r'^Cannot get the token of the test: invalid_grant: Bad$'),
        'error of OAuth 2.0',
    )
    throws_ok(
        lambda: Response(400, b'{"error": "invalid_scope"}').credentials(),
        re.compile(r'^Cannot get the token of the test: invalid_scope$'),
        'error without a description',
    )
    throws_ok(
        lambda: Response(200, b'{"token_type": "Bearer"}').credentials(),
        re.compile(r'^Cannot get the token of the test: no access_token$'),
        'response without a token',
    )
    throws_ok(
        lambda: Response(503, b'Unavailable').credentials(),
        re.compile(r'^Cannot get the token of the test: 503'),
        'response that is not JSON',
    )

with subtest('Authorized user'):
    REQUESTS.clear()
    provider = Pyjo.GCP.Credentials.AuthorizedUser.AuthorizedUser.from_info(
        Pyjo.JSON.from_json(user(quota_project_id='quota', account='me@example.com', universe_domain='googleapis.com')),
        ua=ua,
    )
    credentials = provider.credentials()
    is_ok(credentials.token, 'ya29.refresh', 'access token')
    ok(3500 < credentials.expires_in() <= 3599, 'expiration')
    is_ok(
        (credentials.quota_project, credentials.account, credentials.universe_domain, credentials.provider),
        ('quota', 'me@example.com', 'googleapis.com', 'authorized_user'),
        'fields of the file',
    )
    is_ok(
        REQUESTS,
        [{'grant_type': 'refresh_token', 'client_id': 'client', 'client_secret': 'secret', 'refresh_token': 'refresh'}],
        'form of the refresh token, without scopes',
    )
    is_ok(
        Pyjo.GCP.Credentials.AuthorizedUser.new(client_id='a', client_secret='b', refresh_token='c').token_uri,
        'https://oauth2.googleapis.com/token',
        'token endpoint of Google',
    )

    provider = Pyjo.GCP.Credentials.AuthorizedUser.AuthorizedUser.from_info(Pyjo.JSON.from_json(user('rotate')), ua=ua)
    result = wait(provider.credentials_p())
    is_ok(result['value'].token, 'ya29.rotate', 'access token, non-blocking')
    is_ok(provider.refresh_token, 'rotated', 'new refresh token')

    for name, refresh_token, error in (
        ('revoked', 'revoked', r'invalid_grant: Token has been expired or revoked\.'),
        ('status', 'broken', r'502 Bad Gateway'),
    ):
        provider = Pyjo.GCP.Credentials.AuthorizedUser.AuthorizedUser.from_info(
            Pyjo.JSON.from_json(user(refresh_token)), ua=ua
        )
        throws_ok(
            lambda provider=provider: provider.credentials(),
            re.compile(rf'^Cannot get the token of an authorized user: {error}'),
            f'error, {name}',
        )

    throws_ok(
        lambda: Pyjo.GCP.Credentials.AuthorizedUser.AuthorizedUser.from_info({'type': 'authorized_user'}),
        re.compile(r'^Invalid credentials of an authorized user: no client_id, client_secret, refresh_token$'),
        'file without its fields',
    )

with subtest('File'):
    with environ():
        config = Pyjo.GCP.Config.new()
        is_ok(Pyjo.GCP.Credentials.File.new(config=config).credentials(), None, 'no path')
        missing = str(tmp.child('missing.json'))
        is_ok(
            Pyjo.GCP.Credentials.File.new(path=missing, optional=True, config=config).credentials(),
            None,
            'optional file that does not exist',
        )
        throws_ok(
            lambda: Pyjo.GCP.Credentials.File.new(path=missing, config=config).credentials(),
            re.compile(r'^Cannot read the credentials of Google Cloud: '),
            'file that does not exist',
        )
        unknown = tmp.child('unknown.json').spew('{"type": "gdch_service_account"}')
        throws_ok(
            lambda: Pyjo.GCP.Credentials.File.new(path=str(unknown), config=config).credentials(),
            re.compile(r"^Unsupported type of the credentials of Google Cloud .*unknown\.json: 'gdch_service_account'"),
            'type that is not supported',
        )

        credentials = Pyjo.GCP.Credentials.File.new(path=str(KEY), config=config, ua=ua).credentials()
        is_ok(credentials.token, 'ya29.explicit', 'credentials of the file')
        is_ok((credentials.quota_project, credentials.project), ('file-quota', None), 'quota project of the file')

        ADC.spew(user('gcloud'))
        provider = Pyjo.GCP.Credentials.File.new(path=config.adc_file(), config=config, ua=ua)
        ok(provider.is_gcloud(), 'file of gcloud')
        is_ok(provider.credentials().project, 'gcloud-project', 'project of the configuration of gcloud')
        is_ok(
            Pyjo.GCP.Credentials.File.new(path=str(KEY), config=config).scopes,
            ['https://www.googleapis.com/auth/cloud-platform'],
            'scopes of cloud-platform',
        )

    with environ(GOOGLE_CLOUD_QUOTA_PROJECT='env-quota', CLOUDSDK_CORE_PROJECT='env-gcloud'):
        config = Pyjo.GCP.Config.new()
        credentials = Pyjo.GCP.Credentials.File.new(path=str(KEY), config=config, ua=ua).credentials()
        is_ok(credentials.quota_project, 'env-quota', 'quota project of the environment')
        is_ok(credentials.project, None, 'no project of gcloud for another file')
        credentials = Pyjo.GCP.Credentials.File.new(path=config.adc_file(), config=config, ua=ua).credentials()
        is_ok(credentials.project, 'env-gcloud', 'property of gcloud of the environment')

with subtest('Chain'):
    with environ():
        ADC.remove()
        is_ok(Pyjo.GCP.Credentials.Chain.new(ua=ua).credentials(), None, 'no credentials')

        ADC.spew(user('gcloud'))
        credentials = Pyjo.GCP.Credentials.Chain.new(ua=ua).credentials()
        is_ok((credentials.token, credentials.project), ('ya29.gcloud', 'gcloud-project'), 'file of gcloud')

    with environ(GOOGLE_APPLICATION_CREDENTIALS=str(KEY)):
        chain = Pyjo.GCP.Credentials.Chain.new(ua=ua)
        credentials = chain.credentials()
        is_ok(credentials.token, 'ya29.explicit', 'file of GOOGLE_APPLICATION_CREDENTIALS first')
        is_ok(credentials.project, None, 'no project of gcloud for another file')
        is_ok(len(chain.providers), 3, 'providers of the files and of the metadata server')
        result = wait(Pyjo.GCP.Credentials.Chain.new(ua=ua).credentials_p())
        is_ok(result['value'].token, 'ya29.explicit', 'credentials, non-blocking')

    with environ(GOOGLE_APPLICATION_CREDENTIALS=str(ADC)):
        credentials = Pyjo.GCP.Credentials.Chain.new(ua=ua).credentials()
        is_ok(credentials.project, 'gcloud-project', 'file of gcloud of GOOGLE_APPLICATION_CREDENTIALS')

    with environ(GOOGLE_APPLICATION_CREDENTIALS=str(tmp.child('missing.json'))):
        throws_ok(
            lambda: Pyjo.GCP.Credentials.Chain.new(ua=ua).credentials(),
            re.compile(r'^Cannot read the credentials of Google Cloud: '),
            'broken file ends the chain',
        )

    with environ(GOOGLE_APPLICATION_CREDENTIALS=str(KEY), GCLOUD_PROJECT='legacy', GOOGLE_CLOUD_PROJECT='env-project'):
        chain = Pyjo.GCP.Credentials.Chain.new(ua=ua)
        is_ok(chain.credentials().project, 'env-project', 'project of the environment')
        is_ok(chain.providers[0].cached.project, None, 'credentials of the provider unchanged')

    with environ():
        scopes = ['https://www.googleapis.com/auth/devstorage.read_only']
        chain = Pyjo.GCP.Credentials.Chain.new(scopes=scopes, ua=ua)
        is_ok([provider.scopes for provider in chain.providers], [scopes, scopes, scopes], 'scopes of the providers')

        class Fixed(Pyjo.GCP.Credentials.Provider.object):
            async def fetch(self):
                return Pyjo.GCP.Credentials.new(token='ya29.fixed', provider='fixed')

        class Nothing(Pyjo.GCP.Credentials.Provider.object):
            async def fetch(self):
                return None

        chain = Pyjo.GCP.Credentials.Chain.new(providers=[Nothing(), Fixed()])
        is_ok(chain.credentials().provider, 'fixed', 'first provider with credentials')

done_testing()
