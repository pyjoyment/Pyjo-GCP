import Pyjo.File
import Pyjo.IOLoop.Server
import Pyjo.UserAgent

from Pyjo.Test import *

import os
import socket
import subprocess
import sys
import time


# The example against Cloud Storage of its own, of STORAGE_EMULATOR_HOST, as fake-gcs-server, with the list of the JSON
# API and the media of the XML API, both in processes of their own, as the example is a server of its own and its
# client a user agent of its own, which a server of a user agent of the test would not answer

tmp = Pyjo.File.tempdir()
ROOT = Pyjo.File.curfile().dirname().dirname().dirname()
EXAMPLE = ROOT.child('examples', 'gcs.py').to_str()

GCS = tmp.child('gcs.py').spew(r"""
import Pyjo.IOLoop

from Pyjo.Util import md5_sum
from Pyjoyment.Lite import *

app.log.level = 'fatal'

# Cloud Storage does not compress its responses, so that the large object comes in chunks
app.renderer.compress = False

PAGE = 2
BIG = bytes(range(256)) * 65536
OBJECTS = {
    'big.bin': ('application/octet-stream', BIG),
    'docs/a b,ü.txt': ('text/plain', b'Special'),
    'docs/index.html': ('text/html', b'<h1>Docs</h1>'),
    'empty.txt': ('text/plain', b''),
    'files/': ('application/x-www-form-urlencoded;charset=UTF-8', b''),
    'files/1.txt': ('text/plain', b'1'),
    'files/2.txt': ('text/plain', b'2'),
    'files/3.txt': ('text/plain', b'3'),
    'files/sub/x.txt': ('text/plain', b'x'),
    'secret.txt': ('text/plain', b'denied'),
    'slow.txt': ('text/plain', b'Slow'),
}


# An emulator takes no credentials, and the example sends none to it
@hook('before_dispatch')
def anonymous(c):
    if c.req.headers.authorization is not None or c.req.headers.header('x-goog-user-project') is not None:
        c.render(json={'error': {'code': 400, 'message': 'Credentials for an emulator'}}, status=400)


# objects.list of the JSON API, of a prefix and a delimiter, in pages
@get('/storage/v1/b/bucket/o')
def list_objects(c):
    prefix, delimiter = c.param('prefix') or '', c.param('delimiter')
    entries = []
    for name in sorted(OBJECTS):
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        if delimiter and delimiter in rest:
            common = ('prefixes', prefix + rest.split(delimiter)[0] + delimiter)
            if common not in entries:
                entries.append(common)
        else:
            entries.append(('items', name))
    start = int(c.param('pageToken') or 0)
    page = entries[start:start + min(PAGE, int(c.param('maxResults') or 1000))]
    result = {'kind': 'storage#objects'}
    if items := [{'name': name} for kind, name in page if kind == 'items']:
        result['items'] = items
    if prefixes := [name for kind, name in page if kind == 'prefixes']:
        result['prefixes'] = prefixes
    if start + len(page) < len(entries):
        result['nextPageToken'] = str(start + len(page))
    c.render(json=result)


def error(c, status, code, message):
    c.res.headers.content_type = 'application/xml; charset=UTF-8'
    c.render(data=f'<Error><Code>{code}</Code><Message>{message}</Message></Error>'.encode(), status=status)


# The media of the XML API, with the headers of the metadata of the object
@get('/bucket/*name')
def get_object(c):
    name = c.param('name')
    if name == 'secret.txt':
        return error(c, 403, 'AccessDenied', 'Access denied.')
    if name not in OBJECTS:
        return error(c, 404, 'NoSuchKey', 'The specified key does not exist.')
    content_type, body = OBJECTS[name]
    headers = c.res.headers
    headers.content_type = content_type
    headers.etag = f'"{md5_sum(body)}"'
    headers.last_modified = 'Wed, 04 Nov 2026 12:00:00 GMT'
    headers.cache_control = 'public, max-age=3600'
    headers.header('x-goog-generation', '1762257600000000')
    if name == 'docs/a b,ü.txt':
        headers.header('Content-Disposition', 'inline; filename="special.txt"')

    # The headers before the content, as Cloud Storage sends them in records of TLS of their own
    if name == 'slow.txt':
        headers.content_length = len(body)
        c.write()
        Pyjo.IOLoop.timer(0.1, lambda loop: c.write(body))
        return
    c.render(data=body)


app.start()
""")


def listen():
    port = Pyjo.IOLoop.Server.object.generate_port()
    return port, f'http://127.0.0.1:{port}'


def wait_for(process, port):
    deadline = time.monotonic() + 30
    while True:
        try:
            socket.create_connection(('127.0.0.1', port), timeout=1).close()
            return
        except OSError:
            if time.monotonic() > deadline or process.poll() is not None:
                raise
            time.sleep(0.1)


# The environment of the example, of the files of the test only, without credentials, which an emulator does not take
env = {
    name: value
    for name, value in os.environ.items()
    if not name.startswith(('GOOGLE_', 'GCLOUD_', 'CLOUDSDK_', 'GCE_', 'GCS_', 'STORAGE_'))
}
env.update(CLOUDSDK_CONFIG=str(tmp.child('gcloud')), HOME=str(tmp), NO_GCE_CHECK='true', PYJO_LOG_LEVEL='fatal')

gcs_port, gcs_url = listen()
app_port, app_url = listen()
gcs = subprocess.Popen(
    [sys.executable, str(GCS), 'daemon', '-l', gcs_url], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)
stderr = tmp.child('stderr')
with stderr.open('w') as log:
    example = subprocess.Popen(
        [
            sys.executable,
            EXAMPLE,
            *('--bucket', 'bucket', '--emulator-host', f'127.0.0.1:{gcs_port}'),
            *('daemon', '-l', app_url),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=log,
    )

ua = Pyjo.UserAgent.new(max_connections=0)

try:
    wait_for(gcs, gcs_port)
    wait_for(example, app_port)

    with subtest('Objects'):
        tx = ua.get(f'{app_url}/big.bin')
        is_ok(tx.res.code, 200, 'large object')
        is_ok(tx.res.body, bytes(range(256)) * 65536, 'content of the large object')
        is_ok(tx.res.headers.content_type, 'application/octet-stream', 'type of the object')
        is_ok(tx.res.headers.content_length, str(256 * 65536), 'length of the object')
        like_ok(tx.res.headers.etag, r'^"[0-9a-f]{32}"$', 'ETag of the object')
        is_ok(tx.res.headers.last_modified, 'Wed, 04 Nov 2026 12:00:00 GMT', 'date of the object')
        is_ok(tx.res.headers.cache_control, 'public, max-age=3600', 'Cache-Control of the metadata')
        is_ok(tx.res.headers.header('Content-Disposition'), None, 'no Content-Disposition of its own')
        is_ok(tx.res.headers.header('x-goog-generation'), None, 'other headers of Cloud Storage left out')

        tx = ua.get(f'{app_url}/docs/a%20b%2C%C3%BC.txt')
        is_ok(tx.res.code, 200, 'name with a space, a comma and UTF-8, in the path of the XML API')
        is_ok(tx.res.text, 'Special', 'content of the name')
        is_ok(tx.res.headers.header('Content-Disposition'), 'inline; filename="special.txt"',
              'Content-Disposition of the metadata')  # fmt: skip

        tx = ua.get(f'{app_url}/slow.txt')
        is_ok(tx.res.code, 200, 'object whose content comes after its headers')
        is_ok(tx.res.text, 'Slow', 'content after the headers')

        tx = ua.get(f'{app_url}/empty.txt')
        is_ok(tx.res.code, 200, 'empty object')
        is_ok(tx.res.body, b'', 'no content')

        tx = ua.get(f'{app_url}/docs/')
        is_ok(tx.res.code, 200, 'index.html of a folder')
        is_ok(tx.res.text, '<h1>Docs</h1>', 'content of index.html')

        # A client that goes away in the middle of a large object, after which the example serves the others
        with socket.create_connection(('127.0.0.1', app_port)) as client:
            client.sendall(b'GET /big.bin HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n')
            ok(client.recv(1024).startswith(b'HTTP/1.1 200 OK'), 'large object to a client that goes away')
        time.sleep(0.5)
        is_ok(ua.get(f'{app_url}/files/1.txt').res.text, '1', 'object after a client that went away')

    with subtest('Folders'):
        tx = ua.get(f'{app_url}/')
        is_ok(tx.res.code, 200, 'root without index.html')
        is_ok(
            [a.text for a in tx.res.dom().find('li a')],
            ['big.bin', 'docs/', 'empty.txt', 'files/', 'secret.txt', 'slow.txt'],
            'folders and objects of the pages of the list',
        )

        tx = ua.get(f'{app_url}/files/')
        is_ok(
            [a.text for a in tx.res.dom().find('li a')],
            ['../', '1.txt', '2.txt', '3.txt', 'sub/'],
            'folder without the empty object of the console',
        )
        is_ok(tx.res.dom().at('a[href$="sub/"]')['href'], '/files/sub/', 'link of a subfolder')

        tx = ua.get(f'{app_url}/docs')
        is_ok(tx.res.code, 302, 'folder without its slash')
        is_ok(tx.res.headers.location, '/docs/', 'redirect to the folder')

    with subtest('Errors'):
        is_ok(ua.get(f'{app_url}/missing').res.code, 404, 'missing object')
        is_ok(ua.get(f'{app_url}/missing/').res.code, 404, 'missing folder')
        is_ok(ua.get(f'{app_url}/secret.txt').res.code, 500, 'error of Cloud Storage')
finally:
    for process in (example, gcs):
        process.terminate()
        process.wait()

is_ok(example.returncode, 0, 'the example stopped and closed its connections')
is_ok(stderr.slurp().decode(), '', 'nothing on the standard error of the example')

done_testing()
