import Pyjo.File
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials.File
import Pyjo.GCP.Credentials.IdentityPool
import Pyjo.IOLoop.Server
import Pyjo.IOLoop.TLS
import Pyjo.JSON
import Pyjo.UserAgent

from Pyjo.GCP.Credentials.IdentityPool import IdentityPool
from Pyjo.Test import *
from Pyjo.Util import b64_encode

import contextlib
import importlib
import os
import re
import socket
import subprocess
import sys
import time


# The credentials of an external account of a certificate of X.509, of Workload Identity Federation with mTLS, against
# the STS of Google of its own over TLS in a process of its own, with the certificate of the servers of Pyjoyment, which
# takes the requests with the certificate of the workload of the test only, made of its key when it runs, as the one of
# Pyjoyment is of serverAuth, which a server does not take of a client

sys.path.insert(0, Pyjo.File.curfile().dirname().child('lib').to_str())
Key = importlib.import_module('Key')

tmp = Pyjo.File.tempdir()

LEAF = Key.certificate('localhost', 1)
CA = Key.certificate('Pyjo-GCP test CA', 2)
CERT = tmp.child('cert.pem').spew(Key.pem('CERTIFICATE', LEAF))
KEY = tmp.child('key.pem').spew(Key.pem('PRIVATE KEY', Key.PKCS8))
CHAIN = tmp.child('chain.pem').spew(Key.pem('CERTIFICATE', LEAF) + Key.pem('CERTIFICATE', CA))
WRONG_CHAIN = tmp.child('wrong-chain.pem').spew(Key.pem('CERTIFICATE', CA) + Key.pem('CERTIFICATE', LEAF))
TWO = tmp.child('two.pem').spew(Key.pem('CERTIFICATE', LEAF) + Key.pem('CERTIFICATE', CA))
SERVER_CA = Pyjo.File.path(Pyjo.IOLoop.TLS.CERT).sibling('ca.crt').to_str()

AUDIENCE = '//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/x509'
TARGET = 'reader@myproject.iam.gserviceaccount.com'

SERVER = tmp.child('server.py').spew("""\
from Pyjoyment.Lite import *

app.log.level = 'fatal'
calls = []


@post('/v1/token')
def token(c):
    calls.append({'path': '/v1/token', 'form': c.req.params.to_dict()})
    c.render(json={'access_token': 'ya29.x509', 'expires_in': 3599, 'token_type': 'Bearer'})


@post('/v1/projects/-/serviceAccounts/<*name>')
def iam(c):
    calls.append({'path': 'iam', 'authorization': c.req.headers.authorization})
    c.render(json={'accessToken': 'ya29.impersonated', 'expireTime': '2099-01-01T00:00:00Z'})


@get('/crm/<number>')
def crm(c):
    c.render(json={'projectId': 'myproject'})


@get('/calls')
def calls_action(c):
    c.render(json=calls)


app.start()
""")


def listen():
    port = Pyjo.IOLoop.Server.object.generate_port()
    return port, f'https://127.0.0.1:{port}'


port, base = listen()
server = subprocess.Popen(
    [sys.executable, str(SERVER), 'daemon', '-l', f'{base}?ca={CERT}'],
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

# The user agent of the provider, of the authority of the certificate of Pyjoyment, to which the provider adds the
# certificate of the workload; the one of the test presents it too, as the server takes no request without it
ua = Pyjo.UserAgent.new(ca=SERVER_CA, max_connections=0)
control = Pyjo.UserAgent.new(ca=SERVER_CA, cert=str(CERT), key=str(KEY), max_connections=0)


def calls():
    return control.get(f'{base}/calls').res.json()


def config(name='certificate_config.json', **workload):
    path = tmp.child(name)
    path.spew(
        Pyjo.JSON.to_json({'cert_configs': {'workload': {'cert_path': str(CERT), 'key_path': str(KEY), **workload}}})
    )
    return str(path)


@contextlib.contextmanager
def environ(**values):
    saved = dict(os.environ)
    try:
        for name in list(os.environ):
            if name.startswith(('GOOGLE_', 'GCLOUD_', 'CLOUDSDK_', 'GCE_')):
                del os.environ[name]
        os.environ.update({'CLOUDSDK_CONFIG': str(tmp.child('gcloud')), 'HOME': str(tmp.child('home')),
                           'NO_GCE_CHECK': 'True', **values})  # fmt: skip
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


def info(**certificate):
    return {
        'type': 'external_account',
        'audience': AUDIENCE,
        'subject_token_type': Pyjo.GCP.Credentials.IdentityPool.MTLS,
        'token_url': f'{base}/v1/token',
        'credential_source': {'certificate': {'certificate_config_location': config(), **certificate}},
    }


def provider_of(fields):
    provider = Pyjo.GCP.Credentials.File.new(config=Pyjo.GCP.Config.new(), ua=ua).provider_of(fields)
    provider.project_url = f'{base}/crm/'
    return provider


def token(*certificates):
    return '[' + ','.join(f'"{b64_encode(der, "")}"' for der in certificates) + ']'


try:
    with environ():
        with subtest('Exchange of mTLS'):
            provider = provider_of(info())
            ok(isinstance(provider, IdentityPool) and provider.certificate, 'identity pool of a certificate')
            is_ok((provider.ua.cert, provider.ua.key), (str(CERT), str(KEY)), 'user agent of the certificate')
            credentials = provider.credentials()
            is_ok((credentials.token, credentials.project), ('ya29.x509', 'myproject'), 'token over mTLS')
            form = calls()[-1]['form']
            is_ok(
                (form['subject_token_type'], form['subject_token']),
                ('urn:ietf:params:oauth:token-type:mtls', token(LEAF)),
                'subject token of the certificate, in Base64 of DER',
            )
            result = wait(provider_of(info()).credentials_p())
            is_ok(result['value'].token, 'ya29.x509', 'token, non-blocking')

            throws_ok(
                lambda: Pyjo.UserAgent.new(ca=SERVER_CA, max_connections=0).post(f'{base}/v1/token').result,
                re.compile(r''),
                'no request of the server without the certificate',
            )

            provider_of(info(trust_chain_path=str(CHAIN))).credentials()
            is_ok(calls()[-1]['form']['subject_token'], token(LEAF, CA), 'trust chain after the certificate, once')

            url = f'{base}/v1/projects/-/serviceAccounts/{TARGET}:generateAccessToken'
            credentials = provider_of({**info(), 'service_account_impersonation_url': url}).credentials()
            is_ok((credentials.token, credentials.account), ('ya29.impersonated', TARGET), 'impersonation over mTLS')

        with subtest('Configuration of the certificate'):
            provider = provider_of(info())
            is_ok(provider.certificate_paths(), (str(CERT), str(KEY)), 'configuration of the file')

            with environ(GOOGLE_API_CERTIFICATE_CONFIG=config('env.json')):
                default = info(certificate_config_location=None, use_default_certificate_config=True)
                is_ok(provider_of(default).certificate_config_location, None, 'default configuration')
                is_ok(
                    provider_of(default).credentials().token,
                    'ya29.x509',
                    'configuration of GOOGLE_API_CERTIFICATE_CONFIG',
                )

            with environ(CLOUDSDK_CONTEXT_AWARE_CERTIFICATE_CONFIG_FILE_PATH=config('gcloud.json')):
                is_ok(provider_of(default).credentials().token, 'ya29.x509',
                      'configuration of CLOUDSDK_CONTEXT_AWARE_CERTIFICATE_CONFIG_FILE_PATH')  # fmt: skip

            home = tmp.child('home', '.config', 'gcloud').make_path()
            home.child('certificate_config.json').spew(tmp.child('certificate_config.json').slurp())
            is_ok(provider_of(default).credentials().token, 'ya29.x509', 'configuration of ~/.config/gcloud')

            cloud_run = config(
                'cloud-run.json',
                cert_path='/var/lib/volumes/certificate/workload-certificates/certificates.pem',
                key_path='/var/lib/volumes/certificate/workload-certificates/private_key.pem',
            )
            is_ok(
                provider_of(info(certificate_config_location=cloud_run)).certificate_paths(),
                (Pyjo.GCP.Credentials.IdentityPool.CLOUD_RUN_CERT, Pyjo.GCP.Credentials.IdentityPool.CLOUD_RUN_KEY),
                'well-known files of Cloud Run of the configuration of gcloud before',
            )

        with subtest('Errors'):
            errors = [
                (info(certificate_config_location=str(tmp.child('missing.json'))), r'no configuration of the certificate \S+missing\.json'),
                (info(certificate_config_location=str(tmp.child('invalid.json').spew('{'))), r'cannot parse \S+invalid\.json'),
                (info(certificate_config_location=str(tmp.child('empty.json').spew('{}'))), r'no cert_configs\.workload of \S+empty\.json'),
                (info(certificate_config_location=config('no-key.json', key_path=None)), r'no cert_path or key_path'),
            ]  # fmt: skip
            for fields, error in errors:
                throws_ok(
                    lambda fields=fields: provider_of(fields),
                    re.compile(r'^Invalid certificate of an external account: ' + error),
                    error,
                )

            throws_ok(
                lambda: provider_of(
                    info(certificate_config_location=config('two.json', cert_path=str(TWO)))
                ).credentials(),
                re.compile(r'^Invalid certificate of an external account: not one certificate of PEM in \S+two\.pem'),
                'file of more than one certificate',
            )
            throws_ok(
                lambda: provider_of(info(trust_chain_path=str(WRONG_CHAIN))).credentials(),
                re.compile(r'^Invalid certificate of an external account: the certificate of the workload not first'),
                'certificate after another one in the trust chain',
            )
            throws_ok(
                lambda: provider_of(info(use_default_certificate_config=True)),
                re.compile(r'^Invalid credentials of an external account: one of certificate_config_location and'),
                'both the location and the default of the configuration',
            )
            throws_ok(
                lambda: provider_of(info(certificate_config_location=None)),
                re.compile(r'^Invalid credentials of an external account: one of certificate_config_location and'),
                'none of the location and the default of the configuration',
            )
finally:
    server.terminate()
    server.wait()

done_testing()
