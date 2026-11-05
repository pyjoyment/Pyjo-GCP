import Pyjo.File
import Pyjo.GCP.Call
import Pyjo.GCP.Client
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials.File
import Pyjo.GCP.Credentials.IdentityPool
import Pyjo.GCP.X509
import Pyjo.IOLoop.Server
import Pyjo.IOLoop.TLS
import Pyjo.JSON
import Pyjo.UserAgent
import Pyjo.Util

from Pyjo.GCP.Credentials.IdentityPool import IdentityPool
from Pyjo.Test import *

import contextlib
import importlib
import os
import re
import socket
import subprocess
import sys
import time


# The credentials of an external account of a certificate of X.509, of Workload Identity Federation with mTLS, against
# the STS of Google of its own over TLS in a process of its own, with the certificates of the package of Pyjoyment: the
# server of server.crt, which takes the requests with client.crt only, the certificate of the workload, as ca.crt signs
# both

tmp = Pyjo.File.tempdir()

CERTS = Pyjo.File.path(Pyjo.IOLoop.TLS.CERT).dirname()
CA, CERT, KEY = (CERTS.child(name).to_str() for name in ('ca.crt', 'client.crt', 'client.key'))
CHAIN = tmp.child('chain.pem').spew(Pyjo.File.path(CERT).slurp() + Pyjo.File.path(CA).slurp())
WRONG_CHAIN = tmp.child('wrong-chain.pem').spew(Pyjo.File.path(CA).slurp() + Pyjo.File.path(CERT).slurp())

# The certificate of an agent identity, of the SPIFFE ID of an agent, which Pyjoyment has not, made of the key of the
# tests when the test runs, which the server takes as an authority of its own too
sys.path.insert(0, Pyjo.File.curfile().dirname().child('lib').to_str())
Key = importlib.import_module('Key')
AGENT_URI = 'spiffe://agents.global.proj-123456.system.id.goog/resources/aiplatform/agent'
AGENT = tmp.child('agent.pem').spew(Key.pem('CERTIFICATE', Key.certificate('agent', [AGENT_URI])))
AGENT_KEY = tmp.child('agent.key').spew(Key.pem('PRIVATE KEY', Key.PKCS8))
AUTHORITIES = tmp.child('authorities.pem').spew(Pyjo.File.path(CA).slurp() + AGENT.slurp())

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


@get('/storage/v1/b')
def buckets(c):
    c.render(json={'items': [{'name': 'mybucket'}]})


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
    [sys.executable, str(SERVER), 'daemon', '-l', f'{base}?ca={AUTHORITIES}'],
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

# The user agent of the provider, of the authority of Pyjoyment, to which the provider adds the certificate of the
# workload; the one of the test presents it too, as the server takes no request without it
ua = Pyjo.UserAgent.new(ca=CA, max_connections=0)
control = Pyjo.UserAgent.new(ca=CA, cert=CERT, key=KEY, max_connections=0)


def calls():
    return control.get(f'{base}/calls').res.json()


def config(name='certificate_config.json', **workload):
    path = tmp.child(name)
    path.spew(Pyjo.JSON.to_json({'cert_configs': {'workload': {'cert_path': CERT, 'key_path': KEY, **workload}}}))
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


# The subject token of certificates of PEM, each one in Base64 of DER, which is the one of the PEM without its lines
def token(*paths):
    certificates = []
    for path in paths:
        pem = Pyjo.File.path(path).slurp('UTF-8') or ''
        body = pem.split('-----BEGIN CERTIFICATE-----')[1].split('-----END CERTIFICATE-----')[0]
        certificates.append('"' + ''.join(body.split()) + '"')
    return '[' + ','.join(certificates) + ']'


try:
    with environ():
        with subtest('Exchange of mTLS'):
            provider = provider_of(info())
            ok(isinstance(provider, IdentityPool) and provider.certificate, 'identity pool of a certificate')
            is_ok((provider.ua.cert, provider.ua.key), (CERT, KEY), 'user agent of the certificate')
            credentials = provider.credentials()
            is_ok((credentials.token, credentials.project), ('ya29.x509', 'myproject'), 'token over mTLS')
            form = calls()[-1]['form']
            is_ok(
                (form['subject_token_type'], form['subject_token']),
                ('urn:ietf:params:oauth:token-type:mtls', token(CERT)),
                'subject token of the certificate, in Base64 of DER',
            )
            result = wait(provider_of(info()).credentials_p())
            is_ok(result['value'].token, 'ya29.x509', 'token, non-blocking')

            throws_ok(
                lambda: Pyjo.UserAgent.new(ca=CA, max_connections=0).post(f'{base}/v1/token').result,
                re.compile(r''),
                'no request of the server without the certificate',
            )

            provider_of(info(trust_chain_path=str(CHAIN))).credentials()
            is_ok(calls()[-1]['form']['subject_token'], token(CERT, CA), 'trust chain after the certificate, once')

            url = f'{base}/v1/projects/-/serviceAccounts/{TARGET}:generateAccessToken'
            credentials = provider_of({**info(), 'service_account_impersonation_url': url}).credentials()
            is_ok((credentials.token, credentials.account), ('ya29.impersonated', TARGET), 'impersonation over mTLS')

        with subtest('Configuration of the certificate'):
            provider = provider_of(info())
            is_ok(provider.certificate_paths(), (CERT, KEY), 'configuration of the file')

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
                (Pyjo.GCP.Config.CLOUD_RUN_CERT, Pyjo.GCP.Config.CLOUD_RUN_KEY),
                'well-known files of Cloud Run of the configuration of gcloud before',
            )

        with subtest('Errors'):
            errors = [
                (info(certificate_config_location=str(tmp.child('missing.json'))), r'^Invalid certificate of an external account: no configuration of the certificate \S+missing\.json'),
                (info(certificate_config_location=str(tmp.child('invalid.json').spew('{'))), r'^Invalid configuration of the certificate of Google Cloud: cannot parse \S+invalid\.json'),
                (info(certificate_config_location=str(tmp.child('empty.json').spew('{}'))), r'^Invalid configuration of the certificate of Google Cloud: no cert_configs\.workload of \S+empty\.json'),
                (info(certificate_config_location=config('no-key.json', key_path=None)), r'^Invalid configuration of the certificate of Google Cloud: no cert_path or key_path'),
            ]  # fmt: skip
            for fields, error in errors:
                throws_ok(lambda fields=fields: provider_of(fields), re.compile(error), error.lstrip('^'))

            throws_ok(
                lambda: provider_of(
                    info(certificate_config_location=config('two.json', cert_path=str(CHAIN)))
                ).credentials(),
                re.compile(r'^Invalid certificate of an external account: not one certificate of PEM in \S+chain\.pem'),
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

    # The calls of a client with the certificate of the workload, of GOOGLE_API_USE_CLIENT_CERTIFICATE or of the
    # configuration of GOOGLE_API_CERTIFICATE_CONFIG, to the same server, which takes them with it only
    # The token of the exchange bound to the certificate of the agent identity of the workload, of the options of
    # bindCertFingerprint of its fingerprint, as google-auth has them
    with subtest('Agent identity'):
        with environ():
            agent = config('agent.json', cert_path=str(AGENT), key_path=str(AGENT_KEY))
            is_ok(
                provider_of(info(certificate_config_location=agent)).credentials().token,
                'ya29.x509',
                'token of the agent',
            )
            options = Pyjo.JSON.from_json(Pyjo.Util.url_unescape(calls()[-1]['form']['options']))
            is_ok(options, {'bindCertFingerprint': Pyjo.GCP.X509.from_pem(AGENT.slurp()).fingerprint()},
                  'fingerprint of the certificate of the agent')  # fmt: skip
            provider_of(info()).credentials()
            ok('options' not in calls()[-1]['form'], 'no fingerprint of a workload that is not an agent')

        with environ(GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES='false'):
            provider_of(info(certificate_config_location=agent)).credentials()
            ok(
                'options' not in calls()[-1]['form'],
                'no fingerprint of GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES',
            )

    with subtest('Client of mTLS'):
        call = Pyjo.GCP.Call.new('GET', '/storage/v1/b')
        with environ(GOOGLE_API_CERTIFICATE_CONFIG=config('client.json')):
            client = Pyjo.GCP.Client.new(service='storage', endpoint=base, anonymous=True,
                                         ua=Pyjo.UserAgent.new(ca=CA, max_connections=0))  # fmt: skip
            is_ok(
                client.client_certificate,
                (CERT, KEY),
                'certificate of the configuration of GOOGLE_API_CERTIFICATE_CONFIG',
            )
            is_ok((client.ua.cert, client.ua.key), (CERT, KEY), 'certificate of the user agent')
            is_ok(client.call(call)['items'][0]['name'], 'mybucket', 'call over mTLS')
            result = wait(client.call_p(call))
            is_ok(result['value']['items'][0]['name'], 'mybucket', 'call over mTLS, non-blocking')
            is_ok(Pyjo.GCP.Client.new(service='storage').endpoint_url(), 'https://storage.mtls.googleapis.com',
                  'endpoint of mTLS')  # fmt: skip

        with environ(GOOGLE_API_CERTIFICATE_CONFIG=config('client.json'), GOOGLE_API_USE_CLIENT_CERTIFICATE='false'):
            client = Pyjo.GCP.Client.new(service='storage', endpoint=base, anonymous=True,
                                         ua=Pyjo.UserAgent.new(ca=CA, max_connections=0))  # fmt: skip
            is_ok(
                (client.client_certificate, client.ua.cert),
                (None, None),
                'no certificate of GOOGLE_API_USE_CLIENT_CERTIFICATE',
            )
            throws_ok(lambda: client.call(call), re.compile(r''), 'no call of the server without the certificate')
            is_ok(Pyjo.GCP.Client.new(service='storage').endpoint_url(), 'https://storage.googleapis.com',
                  'endpoint without mTLS')  # fmt: skip
finally:
    server.terminate()
    server.wait()

done_testing()
