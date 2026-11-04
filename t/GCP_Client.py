import Pyjo.Exception
import Pyjo.GCP.Call
import Pyjo.GCP.Client
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials
import Pyjo.GCP.Credentials.Chain
import Pyjo.GCP.Credentials.Provider
import Pyjo.GCP.Error
import Pyjo.Promise
import Pyjo.UserAgent

from Pyjo.GCP.Call import Call
from Pyjo.Test import *
from Pyjoyment.Lite import *

import contextlib
import os
import re


# The client of a JSON API of Google Cloud, with its calls and errors, against an application that serves the JSON API
# of Cloud Storage

app.log.level = 'fatal'

seen = {}


@hook('before_dispatch')
def record(c):
    seen.clear()
    seen.update(
        method=c.req.method,
        path=c.req.url.path.to_str(),
        query=c.req.url.query.to_str(),
        authorization=c.req.headers.authorization,
        quota=c.req.headers.header('x-goog-user-project'),
        body=c.req.body,
    )


def error(c, status, body):
    c.render(json={'error': body}, status=status)


@get('/gcs/storage/v1/b/<bucket>/o')
def list_objects(c):
    if c.param('bucket') != 'mybucket':
        return error(c, 404, {'code': 404, 'message': 'The specified bucket does not exist.',
                              'errors': [{'message': 'The specified bucket does not exist.', 'domain': 'global',
                                          'reason': 'notFound'}]})  # fmt: skip
    c.render(json={'kind': 'storage#objects', 'items': [{'name': 'a.txt'}, {'name': 'docs/b c.txt'}]})


@get('/gcs/storage/v1/b/<bucket>/o/<*name>')
def get_object(c):
    if c.param('alt') == 'media':
        return c.render(data=b'Hello', format='txt')
    c.render(json={'name': c.param('name'), 'bucket': c.param('bucket')})


@post('/gcs/storage/v1/b')
def insert_bucket(c):
    c.render(json={'name': c.req.json('/name'), 'project': c.param('project')})


@delete('/gcs/storage/v1/b/<bucket>')
def delete_bucket(c):
    c.rendered(204)


@get('/gcs/disabled')
def disabled(c):
    error(c, 403, {'code': 403, 'message': 'Cloud Storage API has not been used in project 123.',
                   'status': 'PERMISSION_DENIED',
                   'details': [{'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': 'SERVICE_DISABLED',
                                'domain': 'googleapis.com'}]})  # fmt: skip


@get('/gcs/gateway')
def gateway(c):
    c.render(text='Bad Gateway', status=502)


class Static(Pyjo.GCP.Credentials.Provider.object):
    def __init__(self, **fields):
        super().__init__()
        self.fields = fields
        self.count = 0

    async def fetch(self):
        self.count += 1
        return Pyjo.GCP.Credentials.new(token='ya29.static', provider='static', **self.fields)


class Nothing(Pyjo.GCP.Credentials.Provider.object):
    async def fetch(self):
        return None


ua = Pyjo.UserAgent.new()
ua.server.app = app


# A relative endpoint, which the user agent resolves to its server of the blocking or the non-blocking requests
def client(**kwargs):
    kwargs.setdefault('endpoint', '/gcs')
    kwargs.setdefault('credentials', Static())
    kwargs.setdefault('ua', ua)
    return Pyjo.GCP.Client.new(service='storage', **kwargs)


@contextlib.contextmanager
def environ(**values):
    saved = dict(os.environ)
    try:
        for name in list(os.environ):
            if name.startswith(('GOOGLE_', 'GCLOUD_', 'CLOUDSDK_', 'GCE_')) or name.endswith('_EMULATOR_HOST'):
                del os.environ[name]
        os.environ.update({'CLOUDSDK_CONFIG': os.devnull, 'NO_GCE_CHECK': 'True', **values})
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


def error_of(cb):
    try:
        cb()
    except Pyjo.GCP.Error.object as e:
        return e
    return None


with subtest('Endpoint'):
    with environ():
        storage = Pyjo.GCP.Client.new(service='storage')
        is_ok(storage.endpoint_url(), 'https://storage.googleapis.com', 'endpoint of Google')
        ok(not storage.anonymous, 'with credentials')
        ok(isinstance(storage.credentials, Pyjo.GCP.Credentials.Chain.object), 'credentials of the chain')
        ok(storage.credentials.ua is storage.ua, 'user agent of the client')
        scopes = ['https://www.googleapis.com/auth/devstorage.read_only']
        is_ok(Pyjo.GCP.Client.new(service='storage', scopes=scopes).credentials.scopes, scopes, 'scopes of the chain')
        is_ok(Pyjo.GCP.Client.new(service='iam', endpoint='/iam').endpoint_url(), '/iam', 'endpoint of the client')

    with environ(GOOGLE_CLOUD_UNIVERSE_DOMAIN='example.goog'):
        is_ok(Pyjo.GCP.Client.new(service='storage').endpoint_url(), 'https://storage.example.goog', 'universe')

    with environ(STORAGE_EMULATOR_HOST='localhost:4443'):
        storage = Pyjo.GCP.Client.new(service='storage')
        is_ok(storage.endpoint_url(), 'http://localhost:4443', 'endpoint of the emulator')
        ok(storage.anonymous, 'emulator without credentials')
        ok(not Pyjo.GCP.Client.new(service='storage', endpoint='/gcs').anonymous, 'endpoint over the emulator')
        ok(not Pyjo.GCP.Client.new(service='storage', anonymous=False).anonymous, 'emulator with credentials')
        ok(not Pyjo.GCP.Client.new(service='pubsub').anonymous, 'service without an emulator')

with subtest('Calls'):
    storage = client(credentials=Static(quota_project='quota'))
    objects = storage.call(Call('GET', '/storage/v1/b/mybucket/o', query={'prefix': 'docs/', 'versions': False}))
    is_ok([item['name'] for item in objects['items']], ['a.txt', 'docs/b c.txt'], 'result of JSON')
    is_ok(seen['path'], '/gcs/storage/v1/b/mybucket/o', 'path after the one of the endpoint')
    is_ok(seen['query'], 'prefix=docs%2F&versions=false', 'query with a boolean')
    is_ok(seen['authorization'], 'Bearer ya29.static', 'token')
    is_ok(seen['quota'], 'quota', 'quota project')

    storage.call(Call('GET', '/storage/v1/b/mybucket/o?alt=json', query={'fields': ['items', 'prefixes'], 'x': None}))
    is_ok(seen['query'], 'alt=json&fields=items&fields=prefixes', 'query of the path, a list and no None')

    is_ok(
        storage.call(Call('GET', '/storage/v1/b/mybucket/o/docs%2Fb%20c.txt')),
        {'name': 'docs/b c.txt', 'bucket': 'mybucket'},
        'name of a segment percent-encoded',
    )
    is_ok(seen['path'], '/gcs/storage/v1/b/mybucket/o/docs%2Fb%20c.txt', 'path as it is')
    is_ok(storage.call(Call('GET', '/storage/v1/b/mybucket/o/a.txt', query={'alt': 'media'})), b'Hello', 'media')

    bucket = storage.call(Call('POST', '/storage/v1/b', {'name': 'new'}, query={'project': 'myproject'}))
    is_ok(bucket, {'name': 'new', 'project': 'myproject'}, 'JSON of the body')
    is_ok(seen['body'], b'{"name":"new"}', 'body')
    is_ok(storage.call(Call('DELETE', '/storage/v1/b/new')), None, 'no body')

    is_ok(client().call(Call('GET', '/storage/v1/b/mybucket/o/a.txt'))['name'], 'a.txt', 'no quota project')
    is_ok(seen['quota'], None, 'no header of the quota project')

    result = wait(storage.call_p(Call('GET', '/storage/v1/b/mybucket/o')))
    is_ok(len(result['value']['items']), 2, 'non-blocking')
    is_ok(seen['authorization'], 'Bearer ya29.static', 'token, non-blocking')

    credentials = Static()
    storage = client(credentials=credentials)
    wait(Pyjo.Promise.all(*(storage.call_p(Call('GET', '/storage/v1/b/mybucket/o')) for _ in range(3))))
    is_ok(credentials.count, 1, 'credentials once for calls at once')

    anonymous = client(anonymous=True, credentials=Nothing())
    is_ok(anonymous.call(Call('GET', '/storage/v1/b/mybucket/o/a.txt'))['name'], 'a.txt', 'anonymous')
    is_ok(seen['authorization'], None, 'no token')
    result = wait(anonymous.call_p(Call('GET', '/storage/v1/b/mybucket/o/a.txt')))
    is_ok(result['value']['name'], 'a.txt', 'anonymous, non-blocking')

    token = Pyjo.GCP.Credentials.new(token='ya29.given')
    is_ok(client().steps(Call('GET', '/storage/v1/b/mybucket/o/a.txt'), token).run(ua)['name'], 'a.txt', 'steps')
    is_ok(seen['authorization'], 'Bearer ya29.given', 'credentials of the steps')

with subtest('Errors'):
    storage = client()
    e = error_of(lambda: storage.call(Call('GET', '/storage/v1/b/missing/o')))
    is_ok((e.code, e.status, e.reason), (404, None, 'notFound'), 'error of Cloud Storage')
    is_ok(e.message, '404: The specified bucket does not exist.', 'message of the error')
    is_ok(e.tx.res.code, 404, 'transaction of the error')

    e = error_of(lambda: storage.call(Call('GET', '/disabled')))
    is_ok((e.code, e.status, e.reason), (403, 'PERMISSION_DENIED', 'SERVICE_DISABLED'), 'google.rpc.Status')
    is_ok(e.message, '403 PERMISSION_DENIED: Cloud Storage API has not been used in project 123.', 'message')
    is_ok(e.details[0]['domain'], 'googleapis.com', 'details')

    e = error_of(lambda: storage.call(Call('GET', '/gateway')))
    is_ok((e.code, e.status, e.reason, e.details), (502, None, None, []), 'error that is not JSON')
    is_ok(e.message, '502: Bad Gateway', 'message of the status')

    result = wait(storage.call_p(Call('GET', '/storage/v1/b/missing/o')))
    ok(isinstance(result['error'], Pyjo.GCP.Error.object), 'error, non-blocking')
    is_ok(result['error'].reason, 'notFound', 'reason, non-blocking')

    throws_ok(
        lambda: client(credentials=Nothing()).call(Call('GET', '/storage/v1/b/mybucket/o')),
        re.compile(r'^No credentials of Google Cloud: GOOGLE_APPLICATION_CREDENTIALS'),
        'no credentials',
    )
    result = wait(client(credentials=Nothing()).call_p(Call('GET', '/storage/v1/b/mybucket/o')))
    like_ok(str(result['error']), re.compile(r'^No credentials of Google Cloud'), 'no credentials, non-blocking')

    with environ():
        other = Pyjo.GCP.Client.new(service='storage', credentials=Static(universe_domain='example.goog'), ua=ua)
        throws_ok(
            lambda: other.call(Call('GET', '/storage/v1/b/mybucket/o')),
            re.compile(r'^The universe domain of the credentials of Google Cloud example\.goog is not the one of '
                       r'storage googleapis\.com'),
            'credentials of another universe',
        )  # fmt: skip
        is_ok(
            client(credentials=Static(universe_domain='example.goog')).call(Call('GET', '/storage/v1/b/mybucket/o'))[
                'kind'
            ],
            'storage#objects',
            'universe of an endpoint of the client not checked',
        )

    is_ok(Pyjo.GCP.Error.new(None).message, 'Error', 'error without a code')
    is_ok(Pyjo.GCP.Call.value_of(True), 'true', 'value of a boolean')

done_testing()
