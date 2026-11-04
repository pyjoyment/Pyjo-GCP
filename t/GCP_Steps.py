import Pyjo.Exception
import Pyjo.GCP.Steps
import Pyjo.Promise
import Pyjo.UserAgent

from Pyjo.GCP.Steps import Command, Request, Steps
from Pyjo.Test import *
from Pyjoyment.Lite import *

import re
import sys


# The steps of a coroutine or a generator, blocking and non-blocking, against an application of the test

app.log.level = 'fatal'


@get('/token')
def token(c):
    if c.req.headers.header('Metadata-Flavor') != 'Google':
        return c.render(json={'error': 'Forbidden'}, status=403)
    c.render(json={'access_token': 'ya29.test', 'expires_in': 3599})


ua = Pyjo.UserAgent.new()
ua.server.app = app


# The value or the error of a promise, of its own event loop
def wait(promise):
    result = {}
    promise.then(
        lambda *values: result.update(value=values[0] if len(values) == 1 else values),
        lambda reason: result.update(error=reason),
    ).wait()
    return result


async def request(url, flavor='Google'):
    tx = await Request(ua.build_tx('GET', url, {'Metadata-Flavor': flavor}))
    if tx.res.code != 200:
        raise Pyjo.Exception.new(f'Cannot get a token: {tx.res.code}')
    return tx.res.json('/access_token')


with subtest('Requests'):
    is_ok(Steps(request('/token')).run(ua), 'ya29.test', 'request, blocking')
    result = wait(Steps(request('/token')).run_p(ua))
    is_ok(result['value'], 'ya29.test', 'request, non-blocking')

    throws_ok(lambda: Steps(request('/token', 'None')).run(ua), re.compile(r'^Cannot get a token: 403'), 'status')
    result = wait(Steps(request('/token', 'None')).run_p(ua))
    like_ok(str(result['error']), re.compile(r'^Cannot get a token: 403'), 'status, non-blocking')

    async def refused():
        closed = Pyjo.UserAgent.new(connect_timeout=2)
        try:
            await Request(closed.build_tx('GET', 'http://127.0.0.1:1/token'), closed)
        except Pyjo.Exception.object as e:
            return str(e)

    like_ok(
        Steps(refused()).run(ua),
        re.compile(r'^GET http://127\.0\.0\.1:1/token: '),
        'connection error thrown in, blocking',
    )
    result = wait(Steps(refused()).run_p(ua))
    like_ok(
        result['value'], re.compile(r'^GET http://127\.0\.0\.1:1/token: '), 'connection error thrown in, non-blocking'
    )

with subtest('Commands'):

    async def command(*args):
        return await Command([sys.executable, '-c', *args], b'input')

    code, out, err = Steps(command('import sys; print(sys.stdin.read()); sys.exit(3)')).run(ua)
    is_ok((code, out.strip(), err), (3, b'input', b''), 'program, blocking')

    throws_ok(
        lambda: Steps(Command.new(['/nonexistent/gcloud']).__await__()).run(ua),
        re.compile(r'^Cannot run /nonexistent/gcloud: '),
        'program that cannot be run',
    )

    if sys.platform == 'win32':
        skip('the reactor watches no pipes on Windows', 2)
    else:
        result = wait(Steps(command('print("out")')).run_p(ua))
        is_ok((result['value'][0], result['value'][1].strip()), (0, b'out'), 'program, non-blocking')
        result = wait(Steps(Command.new(['/nonexistent/gcloud']).__await__()).run_p(ua))
        like_ok(str(result['error']), re.compile(r'^Cannot run /nonexistent/gcloud: '), 'cannot run, non-blocking')

with subtest('Generators and coroutines'):

    def generated():
        tx = yield Request(ua.build_tx('GET', '/token', {'Metadata-Flavor': 'Google'}))
        code, out, _ = yield Command([sys.executable, '-c', 'print("process")'])
        return f'{tx.res.json("/access_token")} {out.decode().strip()} {code}'

    async def awaited(steps):
        return 'awaited ' + await steps

    def yielded(steps):
        return 'yielded ' + (yield from steps)

    is_ok(Steps(generated()).run(ua), 'ya29.test process 0', 'generator')
    is_ok(
        Steps(yielded(Steps(awaited(Steps(generated()))))).run(ua),
        'yielded awaited ya29.test process 0',
        'generator over coroutine over generator',
    )

    if sys.platform == 'win32':
        skip('the reactor watches no pipes on Windows', 1)
    else:
        result = wait(Steps(awaited(Steps(yielded(Steps(generated()))))).run_p(ua))
        is_ok(result['value'], 'awaited yielded ya29.test process 0', 'coroutine over generator, non-blocking')

    async def promised():
        try:
            await Pyjo.Promise.new()
        except Exception:
            return None

    throws_ok(
        lambda: Steps(promised()).run(ua),
        re.compile(r'^Steps of GCP await \w+: only a Request, a Command and Steps'),
        'promise awaited, not thrown in',
    )
    result = wait(Steps(promised()).run_p(ua))
    ok(isinstance(result['error'], TypeError), 'promise awaited, non-blocking')
    like_ok(str(result['error']), re.compile(r'^Steps of GCP await'), 'error of the promise')

    is_ok(Pyjo.GCP.Steps.Steps, Pyjo.GCP.Steps.object, 'class of the module')

done_testing()
