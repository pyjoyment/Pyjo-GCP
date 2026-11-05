import Pyjo.File
import Pyjo.GCP.Config
import Pyjo.GCP.X509
import Pyjo.IOLoop.TLS
import Pyjo.JSON

from Pyjo.GCP.X509 import Certificate
from Pyjo.Test import *
from Pyjo.Util import b64_encode, sha256_bytes, url_escape

import contextlib
import importlib
import os
import re
import ssl
import sys


# The certificates of X.509 of the workloads and of the agent identities, of the certificate of a client of Pyjoyment
# and of the ones that the key of the tests makes when it runs, which the parser of the module ssl checks

sys.path.insert(0, Pyjo.File.curfile().dirname().child('lib').to_str())
Key = importlib.import_module('Key')

tmp = Pyjo.File.tempdir()

AGENT_URI = 'spiffe://agents.global.proj-123456.system.id.goog/resources/aiplatform/agent'
AGENT = tmp.child('agent.pem').spew(
    Key.pem('CERTIFICATE', Key.certificate('agent', [AGENT_URI, 'https://example.com']))
)
WORKLOAD = tmp.child('workload.pem').spew(
    Key.pem('CERTIFICATE', Key.certificate('workload', ['spiffe://myproject.svc.id.goog/ns/default/sa/app']))
)
CLIENT = Pyjo.File.path(Pyjo.IOLoop.TLS.CERT).sibling('client.crt')
EMPTY = tmp.child('empty.pem').spew('')


def config(name, cert):
    path = tmp.child(name)
    path.spew(Pyjo.JSON.to_json({'cert_configs': {'workload': {'cert_path': str(cert), 'key_path': '/key.pem'}}}))
    return str(path)


@contextlib.contextmanager
def environ(**values):
    saved = dict(os.environ)
    try:
        for name in list(os.environ):
            if name.startswith(('GOOGLE_', 'CLOUDSDK_')):
                del os.environ[name]
        os.environ.update(values)
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


with subtest('Certificates'):
    for path in (AGENT, WORKLOAD, CLIENT):
        pem = path.slurp('UTF-8')
        certificate = Certificate.from_pem(pem)
        der = ssl.PEM_cert_to_DER_cert(pem)
        is_ok(certificate.der, der, f'DER of {path.basename()}')
        expected = url_escape(b64_encode(sha256_bytes(der), '').rstrip('='), r'^A-Za-z0-9\-._~/')
        is_ok(certificate.fingerprint(), expected, f'fingerprint of {path.basename()}')
        names = ssl._ssl._test_decode_cert(str(path)).get('subjectAltName', ())  # type: ignore[attr-defined]
        is_ok(certificate.uris(), [value for kind, value in names if kind == 'URI'], f'URIs of {path.basename()}')

    agent = Certificate.from_pem(AGENT.slurp())
    is_ok(agent.uris(), [AGENT_URI, 'https://example.com'], 'URIs of the agent')
    ok(agent.is_agent_identity(), 'agent identity of a project')
    ok(Certificate.from_pem(Key.pem('CERTIFICATE', Key.certificate('org', ['spiffe://agents.global.org-42.system.id.goog/a'])))
       .is_agent_identity(), 'agent identity of an organization')  # fmt: skip
    ok(not Certificate.from_pem(WORKLOAD.slurp()).is_agent_identity(), 'SPIFFE ID of a workload, not of an agent')
    ok(not Certificate.from_pem(CLIENT.slurp()).is_agent_identity(), 'certificate without URIs')
    like_ok(agent.fingerprint(), re.compile(r'^[A-Za-z0-9%/]{43,}$'), 'fingerprint without padding, percent-encoded')
    is_ok(Pyjo.GCP.X509.from_pem(AGENT.slurp()).der, agent.der, 'function of the module')

    throws_ok(lambda: Certificate.from_pem('no PEM'), re.compile(r'^Invalid certificate of X\.509: not PEM'), 'not PEM')
    throws_ok(
        lambda: Certificate.from_pem('-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----').uris(),
        re.compile(r'^Invalid certificate of X\.509: an invalid length of DER'),
        'truncated DER',
    )

with subtest('Fingerprint of an agent identity'):
    with environ():
        is_ok(Pyjo.GCP.X509.agent_fingerprint(), None, 'no configuration of the certificate')
        ok(Pyjo.GCP.X509.should_bind(), 'bound by default')

    with environ(GOOGLE_API_CERTIFICATE_CONFIG=config('agent.json', AGENT)):
        is_ok(
            Pyjo.GCP.X509.agent_fingerprint(),
            Certificate.from_pem(AGENT.slurp()).fingerprint(),
            'fingerprint of the agent',
        )

    with environ(GOOGLE_API_CERTIFICATE_CONFIG=config('agent.json', AGENT),
                 GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES='False'):  # fmt: skip
        ok(not Pyjo.GCP.X509.should_bind(), 'not bound')
        is_ok(
            Pyjo.GCP.X509.agent_fingerprint(),
            None,
            'no fingerprint of GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES',
        )

    with environ(GOOGLE_API_CERTIFICATE_CONFIG=config('workload.json', WORKLOAD)):
        is_ok(Pyjo.GCP.X509.agent_fingerprint(), None, 'no fingerprint of a workload')

    for name, cert in (('missing.json', tmp.child('missing.pem')), ('empty.json', EMPTY)):
        with environ(GOOGLE_API_CERTIFICATE_CONFIG=config(name, cert)):
            throws_ok(
                Pyjo.GCP.X509.agent_fingerprint,
                re.compile(r'^No certificate of the agent identity of GOOGLE_API_CERTIFICATE_CONFIG: the binding'),
                f'certificate of {name} not there',
            )

done_testing()
