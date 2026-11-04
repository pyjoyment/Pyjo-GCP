"""
__DATA__

@@ folder.html.ep
<!DOCTYPE html>
<html>
  <head><title>/<%= prefix %></title></head>
  <body>
    <h1>/<%= prefix %></h1>
    <ul>
      % if prefix:
      <li><a href="../">../</a></li>
      % end
      % for name in names:
      <li><a href="<%= url_for('object', name=prefix + name) %>"><%= name %></a></li>
      % end
    </ul>
  </body>
</html>
"""

import Pyjo.Exception
import Pyjo.GCP.Call
import Pyjo.GCP.Client
import Pyjo.GCP.Credentials.Chain
import Pyjo.GCP.Credentials.Impersonated
import Pyjo.GCP.Error
import Pyjo.GetOpt
import Pyjo.IOLoop
import Pyjo.UserAgent

from Pyjo.Util import die, getopt, url_escape
from Pyjoyment.Lite import *

import os
import threading


# The options before the command, with the names of the gcloud CLI and the client libraries of Google, which set the
# environment variables that the application reads:
# python gcs.py --impersonate-service-account reader@myproject.iam.gserviceaccount.com --bucket mybucket daemon
getopt(
    {
        'bucket=s': Pyjo.GetOpt.env('GCS_BUCKET'),
        'emulator-host=s': Pyjo.GetOpt.env('STORAGE_EMULATOR_HOST'),
        'impersonate-service-account=s': Pyjo.GetOpt.env('CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT'),
    },
    pass_through=True,
    require_order=True,
)

# The bucket, whose objects the application serves
bucket = os.environ.get('GCS_BUCKET') or die(
    'Usage: gcs.py --bucket BUCKET [--impersonate-service-account EMAIL] [--emulator-host HOST] COMMAND [OPTIONS]'
)
root = '/storage/v1/b/' + url_escape(bucket)

# The token reads the objects only, of a service account or the metadata server, which take scopes; the one of
# gcloud auth application-default login has the scopes of the login
SCOPES = ['https://www.googleapis.com/auth/devstorage.read_only']


# The Application Default Credentials, as the client libraries of Google find them: of GOOGLE_APPLICATION_CREDENTIALS,
# of gcloud auth application-default login, of Workload Identity Federation, or of the metadata server of Compute
# Engine, GKE or Cloud Run; and a token of the service account that they impersonate, as gcloud does with
# --impersonate-service-account, which the client libraries do not read. The source keeps the default scope of the
# chain, cloud-platform, as its token calls the IAM Service Account Credentials API, and only the token of the target
# has the scope of the bucket
def credentials(ua):
    if target := os.environ.get('CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT'):
        source = Pyjo.GCP.Credentials.Chain.new(ua=ua)
        return Pyjo.GCP.Credentials.Impersonated.new(source=source, target_principal=target, scopes=SCOPES, ua=ua)
    return Pyjo.GCP.Credentials.Chain.new(scopes=SCOPES, ua=ua)


# A client of Cloud Storage for each event loop, as the connections of its user agent belong to one, of the endpoint of
# STORAGE_EMULATOR_HOST without a token, as the client libraries of Google take it, with or without its scheme, and
# without x-goog-user-project of the quota project of the credentials: Cloud Storage bills a request with it to that
# project, and gives Cache-Control: no-cache to its response then, not the one of the metadata of the object; a bucket
# of requester pays would need it
local = threading.local()


def gcs():
    if not hasattr(local, 'gcs'):
        ua = Pyjo.UserAgent.new()
        local.gcs = Pyjo.GCP.Client.new(service='storage', credentials=credentials(ua), quota_project=False, ua=ua)
    return local.gcs


# The client closes its connections once the server stops
@hook('after_server_stop')
def after_server_stop(server, app):
    if hasattr(local, 'gcs'):
        local.gcs.ua.close()
        del local.gcs


# The path of an object of the XML API, whose media has the headers of the metadata of the object, where objects.get of
# the JSON API with alt=media gives Content-Disposition: attachment and Cache-Control: no-cache of its own; the name
# keeps its slashes
def path(name):
    return '/' + url_escape(bucket) + '/' + url_escape(name, r'^A-Za-z0-9\-._~/')


# objects.list with the names only, as the resource of an object has its metadata
def list_objects(prefix, **query):
    return Pyjo.GCP.Call.new(
        'GET', root + '/o', query={'prefix': prefix, 'fields': 'items(name),prefixes,nextPageToken', **query}
    )


# The headers of an object that the response has, as Cloud Storage gives them
HEADERS = (
    'Cache-Control',
    'Content-Disposition',
    'Content-Encoding',
    'Content-Language',
    'Content-Length',
    'Content-Type',
    'ETag',
    'Last-Modified',
)


# The media of an object, whose content goes to the client as it comes, each chunk once the client has read the one
# before, so that an object of any size is not kept in memory; the error of the XML API is not JSON, so the call has
# its status only
class GetObject(Pyjo.GCP.Call.object):
    def __init__(self, c, name):
        super().__init__('GET', path(name))
        self.c = c
        self.gone = False

    def build_tx(self, ua, url):
        tx = super().build_tx(ua, url)
        tx.res.content.set(auto_upgrade=False, auto_decompress=False).once('body', lambda content: self.forward(tx))
        return tx

    def forward(self, tx):
        if tx.res.code != 200:
            return
        c, res = self.c, tx.res
        for name in HEADERS:
            if (value := res.headers.header(name)) is not None:
                c.res.headers.header(name, value)
        if res.headers.content_length == '0':
            return c.rendered()

        source = Pyjo.IOLoop.stream(tx.connection)

        # The content emits an empty chunk too, of the end of the headers that come before it, which would end the
        # response
        def read(content, chunk):
            if not chunk:
                return
            source.stop()
            c.write(chunk, lambda c: source.start())

        res.content.unsubscribe('read').on('read', read)

        # A client that goes away before the end of the object closes the connection to Cloud Storage, which reads no
        # more
        def finish(c):
            if not res.is_finished:
                self.gone = True
                Pyjo.IOLoop.remove(tx.connection)

        c.on('finish', finish)

    def parse(self, tx):
        return None


async def send_object(c, name):
    call = GetObject(c, name)
    try:
        await gcs().call_p(call)
    except Pyjo.Exception.object:
        if not call.gone:
            raise


# The folders and the objects under a prefix, of the pages of objects.list, as a bucket without the hierarchical
# namespace has no folders, only names with slashes, and a folder that the console makes, an empty object of the
# prefix, which the list leaves out
async def send_folder(c, prefix):
    names, count, token = [], 0, None
    while True:
        data = await gcs().call_p(list_objects(prefix, delimiter='/', pageToken=token))
        items, prefixes = data.get('items', []), data.get('prefixes', [])
        count += len(items) + len(prefixes)
        names += [p.removeprefix(prefix) for p in prefixes]
        names += [i['name'].removeprefix(prefix) for i in items if i['name'] != prefix]
        if (token := data.get('nextPageToken')) is None:
            break
    if prefix and not count:
        return c.reply.not_found()
    c.render('folder', prefix=prefix, names=sorted(names))


def not_found(e):
    return e.code == 404


# An object, "index.html" or the list of a folder, for a name that ends with a slash
@get('/*name', {'name': ''}, 'object')
async def serve(c):
    name = c.param('name')
    if name and not name.endswith('/'):
        try:
            return await send_object(c, name)
        except Pyjo.GCP.Error.object as e:
            if not not_found(e):
                raise

        # A folder without its slash
        data = await gcs().call_p(list_objects(f'{name}/', maxResults=1))
        if data.get('items') or data.get('prefixes'):
            return c.redirect_to('object', name=f'{name}/')
        return c.reply.not_found()

    try:
        await send_object(c, f'{name}index.html')
    except Pyjo.GCP.Error.object as e:
        if not not_found(e):
            raise
        await send_folder(c, name)


app.start()
