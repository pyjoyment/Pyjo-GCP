import Pyjo.File
import Pyjo.GCP.Config
import Pyjo.GCP.Credentials.AWS
import Pyjo.GCP.Credentials.File
import Pyjo.JSON
import Pyjo.UserAgent

from Pyjo.GCP.Credentials.AWS import AWS
from Pyjo.Test import *
from Pyjo.Util import url_unescape
from Pyjoyment.Lite import *

import contextlib
import datetime
import os
import re


# The credentials of an external account of AWS, of the environment and of the instance metadata of EC2, and the
# signature of the request of GetCallerIdentity, with the STS of Google and the instance metadata of an application of
# the test, and the signatures that RequestSigner of google-auth makes for the same time

tmp = Pyjo.File.tempdir()

app.log.level = 'fatal'

AUDIENCE = '//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/aws'
VERIFICATION_URL = 'https://sts.{region}.amazonaws.com?Action=GetCallerIdentity&Version=2011-06-15'
CALLS = []
REQUESTS = []


@post('/sts/token')
def sts(c):
    REQUESTS.append(Pyjo.JSON.from_json(url_unescape(c.param('subject_token'))))
    CALLS.append(('sts', c.param('subject_token_type')))
    c.render(json={'access_token': 'ya29.aws', 'expires_in': 3599})


@put('/latest/api/token')
def session(c):
    CALLS.append(('session', c.req.headers.header('X-aws-ec2-metadata-token-ttl-seconds')))
    c.render(text='imds-session')


@get('/latest/meta-data/placement/availability-zone')
def zone(c):
    CALLS.append(('zone', c.req.headers.header('X-aws-ec2-metadata-token')))
    c.render(text='eu-west-1b')


@get('/latest/meta-data/iam/security-credentials')
def role(c):
    CALLS.append(('role', c.req.headers.header('X-aws-ec2-metadata-token')))
    c.render(text='my-role')


@get('/latest/meta-data/iam/security-credentials/<role>')
def credentials(c):
    CALLS.append(('credentials', c.param('role'), c.req.headers.header('X-aws-ec2-metadata-token')))
    if c.param('role') != 'my-role':
        return c.rendered(404)
    c.render(json={'AccessKeyId': 'ASIAEXAMPLE', 'SecretAccessKey': 'secret', 'Token': 'imds-token'})


ua = Pyjo.UserAgent.new()
ua.server.app = app

SOURCE = {
    'environment_id': 'aws1',
    'region_url': '/latest/meta-data/placement/availability-zone',
    'url': '/latest/meta-data/iam/security-credentials',
    'regional_cred_verification_url': VERIFICATION_URL,
    'imdsv2_session_token_url': '/latest/api/token',
}


def info(**source):
    return {
        'type': 'external_account',
        'audience': AUDIENCE,
        'subject_token_type': 'urn:ietf:params:aws:token-type:aws4_request',
        'token_url': '/sts/token',
        'credential_source': {**SOURCE, **source},
    }


@contextlib.contextmanager
def environ(**values):
    saved = dict(os.environ)
    try:
        for name in list(os.environ):
            if name.startswith(('GOOGLE_', 'GCLOUD_', 'CLOUDSDK_', 'GCE_', 'AWS_')):
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


def headers(request):
    return {header['key']: header['value'] for header in request['headers']}


with subtest('Signature'):
    url = VERIFICATION_URL.replace('{region}', 'eu-central-1')
    time = datetime.datetime(2026, 11, 4, 12, 34, 56, tzinfo=datetime.UTC).timestamp()
    secret = 'wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY'
    is_ok(
        Pyjo.GCP.Credentials.AWS.sign(url, 'POST', 'eu-central-1', 'AKIDEXAMPLE', secret, None, time),
        {
            'Authorization': 'AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20261104/eu-central-1/sts/aws4_request,'
            ' SignedHeaders=host;x-amz-date, Signature=0adeff6d111c9efdfdb1e98eefd5c62b567276987a97c55b4619c5f430048714',
            'host': 'sts.eu-central-1.amazonaws.com',
            'x-amz-date': '20261104T123456Z',
        },
        'signature of google-auth',
    )
    signed = Pyjo.GCP.Credentials.AWS.sign(url, 'POST', 'eu-central-1', 'AKIDEXAMPLE', secret,
                                           'FwoGZXIvYXdzEXAMPLE//token+=', time)  # fmt: skip
    like_ok(
        signed['Authorization'],
        re.compile(r'SignedHeaders=host;x-amz-date;x-amz-security-token, Signature='
                   r'f7c31dd54c7d92e822bd7bf416f6c552bff7b2594aa0e332d8c45d3d9b9b54e6$'),
        'signature of google-auth with a session token',
    )  # fmt: skip
    is_ok(signed['x-amz-security-token'], 'FwoGZXIvYXdzEXAMPLE//token+=', 'session token')
    throws_ok(
        lambda: Pyjo.GCP.Credentials.AWS.sign('http://sts.amazonaws.com', 'POST', 'us-east-1', 'id', 'secret'),
        re.compile(r'^Invalid URL of AWS of an external account: http://sts\.amazonaws\.com'),
        'URL that is not of HTTPS',
    )

with environ():
    with subtest('Instance metadata'):
        CALLS.clear()
        REQUESTS.clear()
        provider = provider_of(info())
        ok(isinstance(provider, AWS), 'AWS of the type of the subject token')
        is_ok(provider.credentials().token, 'ya29.aws', 'token of AWS')
        is_ok(provider.region, 'eu-west-1', 'region of the availability zone')
        is_ok(
            CALLS,
            [
                ('session', '300'),
                ('zone', 'imds-session'),
                ('session', '300'),
                ('role', 'imds-session'),
                ('credentials', 'my-role', 'imds-session'),
                ('sts', 'urn:ietf:params:aws:token-type:aws4_request'),
            ],
            'requests of IMDSv2',
        )
        request = REQUESTS[0]
        is_ok(
            (request['method'], request['url']),
            ('POST', 'https://sts.eu-west-1.amazonaws.com?Action=GetCallerIdentity&Version=2011-06-15'),
            'request of GetCallerIdentity of the region',
        )
        is_ok(
            [header['key'] for header in request['headers']],
            ['Authorization', 'host', 'x-amz-date', 'x-amz-security-token', 'x-goog-cloud-target-resource'],
            'headers of the request',
        )
        is_ok(
            {name: headers(request)[name] for name in ('host', 'x-amz-security-token', 'x-goog-cloud-target-resource')},
            {'host': 'sts.eu-west-1.amazonaws.com', 'x-amz-security-token': 'imds-token',
             'x-goog-cloud-target-resource': AUDIENCE},
            'values of the headers',
        )  # fmt: skip
        like_ok(headers(request)['Authorization'],
                re.compile(r'^AWS4-HMAC-SHA256 Credential=ASIAEXAMPLE/\d{8}/eu-west-1/sts/aws4_request, '
                           r'SignedHeaders=host;x-amz-date;x-amz-security-token, Signature=[0-9a-f]{64}$'),
                'signature of the credentials of the role')  # fmt: skip

        CALLS.clear()
        provider.cached = None
        provider.credentials()
        is_ok([call[0] for call in CALLS], ['session', 'role', 'credentials', 'sts'], 'region once')

        CALLS.clear()
        result = wait(provider_of(info(imdsv2_session_token_url=None)).credentials_p())
        is_ok(result['value'].token, 'ya29.aws', 'token, non-blocking')
        is_ok(CALLS[:3], [('zone', None), ('role', None), ('credentials', 'my-role', None)], 'requests of IMDSv1')

    with subtest('Errors'):
        throws_ok(
            lambda: provider_of(info(url=None)).credentials(),
            re.compile(r'^No credentials of AWS of an external account: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY'),
            'no credentials',
        )
        throws_ok(
            lambda: provider_of(info(region_url=None)).credentials(),
            re.compile(r'^No region of AWS of an external account: AWS_REGION, AWS_DEFAULT_REGION, or the region_url'),
            'no region',
        )
        throws_ok(
            lambda: provider_of(info(url='/latest/meta-data/iam/missing')).credentials(),
            re.compile(r'^Cannot get the role of AWS of the instance metadata: 404'),
            'error of the instance metadata',
        )
        throws_ok(
            lambda: provider_of(info(regional_cred_verification_url='http://sts.{region}.amazonaws.com')).credentials(),
            re.compile(r'^Invalid URL of AWS of an external account: http://sts\.eu-west-1\.amazonaws\.com'),
            'verification URL that is not of HTTPS',
        )
        invalid = [
            (info(environment_id='aws2'), r'^Unsupported credential_source of an external account: aws2'),
            (info(environment_id='azure1'), r'no environment_id or regional_cred_verification_url of AWS'),
            (info(regional_cred_verification_url=None), r'no environment_id or regional_cred_verification_url of AWS'),
        ]  # fmt: skip
        for fields, error in invalid:
            throws_ok(lambda fields=fields: provider_of(fields), re.compile(error), error.lstrip('^'))

with environ(AWS_ACCESS_KEY_ID='AKIDEXAMPLE', AWS_SECRET_ACCESS_KEY='secret', AWS_SESSION_TOKEN='env-token',
             AWS_DEFAULT_REGION='us-east-2'):  # fmt: skip
    with subtest('Environment'):
        CALLS.clear()
        REQUESTS.clear()
        is_ok(provider_of(info()).credentials().token, 'ya29.aws', 'token of the environment')
        is_ok([call[0] for call in CALLS], ['sts'], 'no instance metadata')
        is_ok(REQUESTS[0]['url'], 'https://sts.us-east-2.amazonaws.com?Action=GetCallerIdentity&Version=2011-06-15',
              'region of AWS_DEFAULT_REGION')  # fmt: skip
        is_ok(headers(REQUESTS[0])['x-amz-security-token'], 'env-token', 'session token of AWS_SESSION_TOKEN')
        os.environ['AWS_REGION'] = 'ap-south-1'
        provider_of(info()).credentials()
        like_ok(REQUESTS[-1]['url'], re.compile(r'^https://sts\.ap-south-1\.'), 'AWS_REGION over AWS_DEFAULT_REGION')

done_testing()
