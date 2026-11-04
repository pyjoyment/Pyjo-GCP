import Pyjo.File
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials.File
import Pyjo.GCP.Credentials.Pluggable
import Pyjo.JSON
import Pyjo.UserAgent

from Pyjo.GCP.Credentials.Pluggable import Pluggable
from Pyjo.Test import *
from Pyjoyment.Lite import *

import contextlib
import os
import re
import shlex
import sys
import time


# The credentials of an external account of an executable, programs of the test that print their output, with the STS
# of Google of an application of the test

tmp = Pyjo.File.tempdir()

app.log.level = 'fatal'

AUDIENCE = '//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/oidc'
JWT = 'urn:ietf:params:oauth:token-type:jwt'
TARGET = 'reader@myproject.iam.gserviceaccount.com'
TOKENS = []


@post('/sts/token')
def sts(c):
    TOKENS.append(c.param('subject_token'))
    c.render(json={'access_token': f'ya29.{c.param("subject_token")}', 'expires_in': 3599})


ua = Pyjo.UserAgent.new()
ua.server.app = app

ENVIRONMENT = tmp.child('environment.json')
EXECUTABLE = tmp.child('executable.py').spew(f"""\
import json, os, sys, time

environment = {{name: value for name, value in os.environ.items() if name.startswith('GOOGLE_EXTERNAL_ACCOUNT_')}}
with open({str(ENVIRONMENT)!r}, 'w') as file:
    file.write(json.dumps(environment))
mode = sys.argv[1]
output = {{'version': 1, 'success': True, 'token_type': 'urn:ietf:params:oauth:token-type:jwt', 'id_token': 'jwt',
          'expiration_time': int(time.time()) + 3600}}
if mode == 'exit':
    print('broken', file=sys.stderr)
    sys.exit(3)
elif mode == 'unsuccessful':
    output = {{'version': 1, 'success': False, 'code': '401', 'message': 'Not allowed'}}
elif mode == 'saml':
    output = {{'version': 1, 'success': True, 'token_type': 'urn:ietf:params:oauth:token-type:saml2',
              'saml_response': 'saml'}}
elif mode == 'version':
    output['version'] = 2
elif mode == 'type':
    output['token_type'] = 'urn:ietf:params:oauth:token-type:access_token'
elif mode == 'expired':
    output['expiration_time'] = 1
elif mode == 'text':
    print('not JSON')
    sys.exit(0)
elif mode == 'sleep':
    time.sleep(10)
if mode == 'file':
    with open(os.environ['GOOGLE_EXTERNAL_ACCOUNT_OUTPUT_FILE'], 'w') as file:
        file.write(json.dumps(output))
else:
    print(json.dumps(output))
""")
OUTPUT = tmp.child('output.json')


def command(mode):
    return f'{shlex.quote(sys.executable)} {shlex.quote(str(EXECUTABLE))} {mode}'


def info(mode='ok', **executable):
    return {
        'type': 'external_account',
        'audience': AUDIENCE,
        'subject_token_type': JWT,
        'token_url': '/sts/token',
        'credential_source': {'executable': {'command': command(mode), **executable}},
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


def provider_of(fields):
    provider = Pyjo.GCP.Credentials.File.new(config=Pyjo.GCP.Config.new(), ua=ua).provider_of(fields)
    provider.project_url = '/crm/'
    return provider


def token(fields):
    return provider_of(fields).credentials().token


with environ(GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES='1'):
    with subtest('Output'):
        provider = provider_of(info())
        ok(isinstance(provider, Pluggable), 'executable of the file')
        is_ok((provider.timeout, provider.output_file), (30, None), '30 seconds by default, no output file')
        is_ok(provider.credentials().token, 'ya29.jwt', 'token of id_token')
        is_ok(
            Pyjo.JSON.decode_json(ENVIRONMENT.slurp()),
            {
                'GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES': '1',
                'GOOGLE_EXTERNAL_ACCOUNT_AUDIENCE': AUDIENCE,
                'GOOGLE_EXTERNAL_ACCOUNT_TOKEN_TYPE': JWT,
                'GOOGLE_EXTERNAL_ACCOUNT_ID': '',
                'GOOGLE_EXTERNAL_ACCOUNT_INTERACTIVE': '0',
                'GOOGLE_EXTERNAL_ACCOUNT_REVOKE': '0',
            },
            'environment of the executable',
        )
        is_ok(token(info('saml')), 'ya29.saml', 'token of saml_response')

        if sys.platform == 'win32':
            skip('the reactor watches no pipes on Windows', 1)
        else:
            result = wait(provider_of(info()).credentials_p())
            is_ok(result['value'].token, 'ya29.jwt', 'token, non-blocking')

        url = f'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{TARGET}:generateAccessToken'
        environment = provider_of(
            {**info(output_file=str(OUTPUT)), 'service_account_impersonation_url': url}
        ).environment()
        is_ok(
            {name: environment.get(name) for name in ('GOOGLE_EXTERNAL_ACCOUNT_ID', 'GOOGLE_EXTERNAL_ACCOUNT_IMPERSONATED_EMAIL',
                                                      'GOOGLE_EXTERNAL_ACCOUNT_OUTPUT_FILE')},
            {'GOOGLE_EXTERNAL_ACCOUNT_ID': TARGET, 'GOOGLE_EXTERNAL_ACCOUNT_IMPERSONATED_EMAIL': TARGET,
             'GOOGLE_EXTERNAL_ACCOUNT_OUTPUT_FILE': str(OUTPUT)},
            'environment of the impersonation and the output file',
        )  # fmt: skip

    with subtest('Output file'):
        if OUTPUT.exists:
            OUTPUT.remove()
        is_ok(token(info('file', output_file=str(OUTPUT))), 'ya29.jwt', 'token of the output file that it writes')
        ENVIRONMENT.remove()
        is_ok(token(info('exit', output_file=str(OUTPUT))), 'ya29.jwt', 'token of the output file kept')
        ok(not ENVIRONMENT.exists, 'without running the executable')

        def output(**fields):
            base = {'version': 1, 'success': True, 'token_type': JWT, 'id_token': 'cached'}
            OUTPUT.spew(Pyjo.JSON.encode_json({**base, **fields}))

        output(expiration_time=1)
        is_ok(token(info(output_file=str(OUTPUT))), 'ya29.jwt', 'executable of an expired output file')
        output()
        is_ok(token(info(output_file=str(OUTPUT))), 'ya29.jwt', 'executable of an output file without expiration')
        OUTPUT.spew('not JSON')
        is_ok(token(info(output_file=str(OUTPUT))), 'ya29.jwt', 'executable of an output file that is not JSON')
        OUTPUT.spew(Pyjo.JSON.encode_json({'success': True}))
        throws_ok(
            lambda: token(info(output_file=str(OUTPUT))),
            re.compile(r'^Invalid credentials of an external account: no version of the output of the executable'),
            'output file of an invalid format',
        )

    with subtest('Errors'):
        errors = [
            ('exit', r'^Cannot run the executable of an external account: exit 3: broken'),
            ('unsuccessful', r'^The executable of an external account failed: 401: Not allowed'),
            ('version', r'^Unsupported version of the output of the executable of an external account: 2'),
            ('type', r'^Unsupported token_type of the output of the executable of an external account: \S+access_token'),
            ('expired', r'^The token of the executable of an external account has expired'),
            ('text', r'^Invalid credentials of an external account: no JSON object of the output of the executable'),
        ]  # fmt: skip
        for mode, error in errors:
            throws_ok(lambda mode=mode: token(info(mode)), re.compile(error), mode)

        start = time.monotonic()
        throws_ok(lambda: token(info('sleep', timeout_millis=5000)), re.compile(r'^Cannot run \S+: no exit in 5 seconds'),
                  'timeout of the executable')  # fmt: skip
        ok(time.monotonic() - start < 9, 'killed at the timeout')

        invalid = [
            ({'command': ''}, r'no command of the executable of the credential_source'),
            ({'command': 'x', 'timeout_millis': 1000}, r'the timeout of the executable 1 seconds, not of 5 to 120'),
            ({'command': 'x', 'timeout_millis': 121000}, r'the timeout of the executable 121 seconds, not of 5 to 120'),
        ]  # fmt: skip
        for executable, error in invalid:
            fields = {**info(), 'credential_source': {'executable': executable}}
            throws_ok(lambda fields=fields: provider_of(fields), re.compile(error), error)

with environ():
    throws_ok(
        lambda: token(info()),
        re.compile(r'^Cannot run the executable of an external account: GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES is not 1'),
        'executables not allowed',
    )  # fmt: skip

done_testing()
