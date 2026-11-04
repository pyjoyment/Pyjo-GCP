import Pyjo.File
import Pyjo.GCP.Credentials.Chain
import Pyjo.GCP.Credentials.Metadata
import Pyjo.IOLoop.Server
import Pyjo.UserAgent

from Pyjo.Test import *

import contextlib
import os
import re
import socket
import subprocess
import sys
import time


# The credentials of the metadata server of Google Cloud, against a server of its own in a process of its own, as the
# provider has a user agent of its own, which a server of a user agent of the test would not answer

tmp = Pyjo.File.tempdir()

SERVER = tmp.child('server.py').spew("""\
from Pyjoyment.Lite import *

app.log.level = 'fatal'
state = {}
calls = []
DEFAULT = {'ping': 'ok', 'token': 'ok', 'universe': None, 'fail': 0}
state.update(DEFAULT)


@hook('before_dispatch')
def record(c):
    if c.req.url.path.to_str() in ('/state', '/calls'):
        return
    calls.append({
        'path': c.req.url.path.to_str(),
        'query': c.req.url.query.to_str(),
        'flavor': c.req.headers.header('Metadata-Flavor'),
    })
    if c.req.headers.header('Metadata-Flavor') != 'Google':
        return c.render(text='Missing Metadata-Flavor', status=403)
    if state['fail'] > 0:
        state['fail'] -= 1
        return c.rendered(503)


@post('/state')
def state_action(c):
    state.clear()
    state.update(DEFAULT)
    state.update(c.req.json())
    calls.clear()
    c.render(json=state)


@get('/calls')
def calls_action(c):
    c.render(json=calls)


@get('/')
def ping(c):
    if state['ping'] == 'ok':
        c.res.headers.header('Metadata-Flavor', 'Google')
    c.render(text='computeMetadata/')


@get('/computeMetadata/v1/instance/service-accounts/<#account>/token')
def token(c):
    if state['token'] == 'denied':
        return c.render(json={'error': 'access_denied', 'error_description': 'No scopes'}, status=403)
    c.render(json={'access_token': f'ya29.{c.param("account")}', 'expires_in': 3599, 'token_type': 'Bearer'})


@get('/computeMetadata/v1/instance/service-accounts/<#account>/email')
def email(c):
    c.render(text='123-compute@developer.gserviceaccount.com')


@get('/computeMetadata/v1/project/project-id')
def project(c):
    c.render(text='metadata-project')


@get('/computeMetadata/v1/universe/universe-domain')
def universe(c):
    if state['universe'] is None:
        return c.rendered(404)
    c.render(text=state['universe'])


app.start()
""")

port = Pyjo.IOLoop.Server.object.generate_port()
base = f'127.0.0.1:{port}'
closed = f'127.0.0.1:{Pyjo.IOLoop.Server.object.generate_port()}'
server = subprocess.Popen(
    [sys.executable, str(SERVER), 'daemon', '-l', f'http://{base}'],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
deadline = time.monotonic() + 30
while True:
    try:
        socket.create_connection(('127.0.0.1', port), timeout=1).close()
        break
    except OSError:
        if time.monotonic() > deadline or server.poll() is not None:
            server.kill()
            raise
        time.sleep(0.1)

control = Pyjo.UserAgent.new(max_connections=0)


def state(**values):
    control.post(f'http://{base}/state', json=values)


def calls():
    return control.get(f'http://{base}/calls').res.json()


@contextlib.contextmanager
def environ(**values):
    saved = dict(os.environ)
    try:
        for name in list(os.environ):
            if name.startswith(('GOOGLE_', 'GCLOUD_', 'CLOUDSDK_', 'GCE_', 'NO_GCE_')):
                del os.environ[name]
        os.environ.update({'CLOUDSDK_CONFIG': str(tmp.child('gcloud')), **values})
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


MISSING = str(tmp.child('missing'))


def Metadata(**kwargs):
    kwargs.setdefault('product_name_file', MISSING)
    return Pyjo.GCP.Credentials.Metadata.new(**kwargs)


try:
    with subtest('Environment'):
        with environ():
            provider = Pyjo.GCP.Credentials.Metadata.new()
            is_ok((provider.host, provider.ip), ('metadata.google.internal', '169.254.169.254'), 'hosts of Google')
            is_ok((provider.timeout, provider.attempts, provider.disabled), (3.0, 3, False), 'defaults of google-auth')
            is_ok(provider.product_name_file, '/sys/class/dmi/id/product_name', 'product of Linux')

        with environ(GCE_METADATA_ROOT='root:1', GCE_METADATA_IP='ip:2', GCE_METADATA_TIMEOUT='0.5',
                     GCE_METADATA_DETECT_RETRIES='2', NO_GCE_CHECK='True'):  # fmt: skip
            provider = Pyjo.GCP.Credentials.Metadata.new()
            is_ok((provider.host, provider.ip), ('root:1', 'ip:2'), 'hosts of the environment')
            is_ok(
                (provider.timeout, provider.attempts, provider.disabled), (0.5, 2, True), 'options of the environment'
            )
            is_ok(provider.credentials(), None, 'NO_GCE_CHECK')
            is_ok(Pyjo.GCP.Credentials.Metadata.new(host='host:3').host, 'host:3', 'host of the argument')

        with environ(GCE_METADATA_HOST='host:1', GCE_METADATA_ROOT='root:1', GCE_METADATA_TIMEOUT='soon'):
            provider = Pyjo.GCP.Credentials.Metadata.new()
            is_ok((provider.host, provider.timeout), ('host:1', 3.0), 'GCE_METADATA_HOST over GCE_METADATA_ROOT')

    with subtest('Token'):
        with environ(GCE_METADATA_HOST=base, GCE_METADATA_IP=base):
            state()
            provider = Metadata()
            credentials = provider.credentials()
            is_ok(credentials.token, 'ya29.default', 'token of the default service account')
            ok(3500 < credentials.expires_in() <= 3599, 'expiration')
            is_ok(
                (credentials.account, credentials.project, credentials.universe_domain, credentials.provider),
                ('123-compute@developer.gserviceaccount.com', 'metadata-project', 'googleapis.com', 'metadata'),
                'email, project and universe of the server',
            )
            is_ok(
                [call['path'] for call in calls()],
                [
                    '/',
                    '/computeMetadata/v1/instance/service-accounts/default/token',
                    '/computeMetadata/v1/instance/service-accounts/default/email',
                    '/computeMetadata/v1/project/project-id',
                    '/computeMetadata/v1/universe/universe-domain',
                ],
                'requests',
            )
            ok(all(call['flavor'] == 'Google' for call in calls()), 'Metadata-Flavor')
            is_ok(calls()[1]['query'], '', 'no scopes')

            state(universe='example.goog')
            provider.cached = None
            is_ok(provider.credentials().universe_domain, 'googleapis.com', 'details once')
            is_ok([call['path'] for call in calls()], ['/computeMetadata/v1/instance/service-accounts/default/token'],
                  'token again only')  # fmt: skip
            is_ok(Metadata().credentials().universe_domain, 'example.goog', 'universe of the server')

            state()
            scopes = ['https://www.googleapis.com/auth/devstorage.read_only', 'https://www.googleapis.com/auth/pubsub']
            result = wait(
                Metadata(scopes=scopes, service_account='reader@myproject.iam.gserviceaccount.com').credentials_p()
            )
            is_ok(result['value'].token, 'ya29.reader@myproject.iam.gserviceaccount.com', 'token, non-blocking')
            is_ok(
                calls()[1]['path'],
                '/computeMetadata/v1/instance/service-accounts/reader@myproject.iam.gserviceaccount.com/token',
                'service account of its email',
            )
            like_ok(
                calls()[1]['query'], re.compile(r'^scopes=https%3A%2F%2F\S+devstorage\.read_only%2Chttps'), 'scopes'
            )

            state(fail=2)
            is_ok(Metadata().credentials().token, 'ya29.default', 'status of 5xx tried again')

            state(token='denied')
            throws_ok(
                lambda: Metadata().credentials(),
                re.compile(r'^Cannot get the token of the metadata server of Google Cloud: access_denied: No scopes'),
                'error of the token',
            )

    with subtest('Detection'):
        with environ(GCE_METADATA_HOST=base, GCE_METADATA_IP=base):
            state(ping='other')
            provider = Metadata(attempts=1)
            is_ok(provider.credentials(), None, 'server without Metadata-Flavor')
            is_ok(provider.detected, False, 'not detected')
            is_ok(len(calls()), 1, 'one request')
            state()
            is_ok(provider.credentials(), None, 'detected once')
            is_ok(calls(), [], 'no request again')

        with environ(GCE_METADATA_HOST=base, GCE_METADATA_IP=closed, GCE_METADATA_TIMEOUT='1'):
            is_ok(Metadata(attempts=1).credentials(), None, 'no server')
            if os.name == 'nt':
                skip('no product of Linux on Windows', 1)
            else:
                product = tmp.child('product_name').spew('Google Compute Engine\n')
                state()
                provider = Metadata(attempts=1, product_name_file=str(product))
                is_ok(provider.credentials().token, 'ya29.default', 'product of Google Compute Engine')

        with environ(GCE_METADATA_HOST=closed, GCE_METADATA_IP=base, GCE_METADATA_TIMEOUT='1'):
            state()
            throws_ok(
                lambda: Metadata(attempts=2).credentials(),
                re.compile(r'^Cannot reach the metadata server of Google Cloud: GET http://127\.0\.0\.1:\d+/'),
                'server of the requests that does not answer',
            )

    with subtest('Chain'):
        with environ(GCE_METADATA_HOST=base, GCE_METADATA_IP=base):
            state()
            chain = Pyjo.GCP.Credentials.Chain.new()
            ok(chain.providers[2].ua is not chain.ua, 'user agent of its own')
            credentials = chain.credentials()
            is_ok((credentials.provider, credentials.project), ('metadata', 'metadata-project'), 'metadata server last')
            like_ok(calls()[1]['query'], re.compile(r'^scopes=https%3A%2F%2Fwww\.googleapis\.com%2Fauth%2Fcloud-platform$'),
                    'scopes of the chain')  # fmt: skip

        with environ(GCE_METADATA_HOST=base, GCE_METADATA_IP=base, GOOGLE_CLOUD_PROJECT='env-project'):
            is_ok(Pyjo.GCP.Credentials.Chain.new().credentials().project, 'env-project', 'project of the environment')
finally:
    server.terminate()
    server.wait()

done_testing()
