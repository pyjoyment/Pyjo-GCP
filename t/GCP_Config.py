import Pyjo.File
import Pyjo.GCP.Config

from Pyjo.Test import *

import contextlib
import os
import re


# The configuration directory of gcloud and the environment of Google Cloud, with files of the test only

tmp = Pyjo.File.tempdir()

GCLOUD = tmp.child('gcloud')
GCLOUD.child('configurations').make_path()
GCLOUD.child('active_config').spew('dev\n')
GCLOUD.child('configurations', 'config_default').spew("""\
[core]
project = default-project
account = me@example.com
""")
GCLOUD.child('configurations', 'config_dev').spew("""\
# A comment
[core]
project = dev-project
disable_usage_reporting = True

[auth]
impersonate_service_account = reader@dev-project.iam.gserviceaccount.com

[api_endpoint_overrides]
storage = http://localhost:4443/storage/v1/
""")
GCLOUD.child('application_default_credentials.json').spew('{"type": "authorized_user", "client_id": "id"}')

KEY = tmp.child('key.json').spew('{"type": "service_account", "project_id": "key-project"}')

NAMES = (
    'APPDATA',
    'CLOUDSDK_ACTIVE_CONFIG_NAME',
    'CLOUDSDK_CONFIG',
    'GCLOUD_PROJECT',
    'GOOGLE_API_CERTIFICATE_CONFIG',
    'GOOGLE_API_USE_CLIENT_CERTIFICATE',
    'GOOGLE_API_USE_MTLS_ENDPOINT',
    'GOOGLE_APPLICATION_CREDENTIALS',
    'GOOGLE_CLOUD_PROJECT',
    'GOOGLE_CLOUD_QUOTA_PROJECT',
    'GOOGLE_CLOUD_UNIVERSE_DOMAIN',
)


# The variables of Google Cloud and gcloud of the environment of the test only, without those of the machine, as
# CLOUDSDK_CORE_PROJECT or STORAGE_EMULATOR_HOST
@contextlib.contextmanager
def environ(**values):
    saved = dict(os.environ)
    try:
        for name in list(os.environ):
            if name in NAMES or name.startswith('CLOUDSDK_') or name.endswith('_EMULATOR_HOST'):
                del os.environ[name]
        os.environ.update({'CLOUDSDK_CONFIG': str(GCLOUD), **values})
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


with subtest('Directory and files'):
    with environ():
        config = Pyjo.GCP.Config.new()
        is_ok(config.config_dir, str(GCLOUD), 'directory of CLOUDSDK_CONFIG')
        is_ok(config.adc_file(), str(GCLOUD.child('application_default_credentials.json')), 'file of gcloud')
        is_ok(config.credentials_file, None, 'no file of GOOGLE_APPLICATION_CREDENTIALS')
        is_ok(config.credentials_info(config.adc_file())['type'], 'authorized_user', 'credentials of gcloud')

    with environ(GOOGLE_APPLICATION_CREDENTIALS=str(KEY)):
        config = Pyjo.GCP.Config.new()
        is_ok(config.credentials_file, str(KEY), 'file of GOOGLE_APPLICATION_CREDENTIALS')
        is_ok(config.credentials_info(str(KEY))['project_id'], 'key-project', 'credentials of the file')
        is_ok(Pyjo.GCP.Config.new(credentials_file='/etc/key.json').credentials_file, '/etc/key.json', 'argument')

    with environ(GOOGLE_APPLICATION_CREDENTIALS=''):
        is_ok(Pyjo.GCP.Config.new().credentials_file, None, 'empty GOOGLE_APPLICATION_CREDENTIALS')

    with environ():
        config = Pyjo.GCP.Config.new()
        throws_ok(
            lambda: config.credentials_info(str(tmp.child('missing.json'))),
            re.compile(r'^Cannot read the credentials of Google Cloud: Can\'t open file ".*missing\.json": '),
            'file that does not exist',
        )
        broken = tmp.child('broken.json').spew('{"type": ')
        throws_ok(
            lambda: config.credentials_info(str(broken)),
            re.compile(r'^Cannot parse the credentials of Google Cloud .*broken\.json: '),
            'file that is not JSON',
        )
        broken.spew('["service_account"]')
        throws_ok(
            lambda: config.credentials_info(str(broken)),
            re.compile(r'^Cannot parse the credentials of Google Cloud .*broken\.json: not an object'),
            'file that is not an object',
        )

    with environ():
        del os.environ['CLOUDSDK_CONFIG']
        home = os.environ.get('HOME')
        os.environ['HOME'] = str(tmp)
        try:
            if os.name == 'nt':
                os.environ['APPDATA'] = str(tmp)
                is_ok(Pyjo.GCP.Config.new().config_dir, str(tmp.child('gcloud')), 'directory of APPDATA')
            else:
                is_ok(Pyjo.GCP.Config.new().config_dir, str(tmp.child('.config', 'gcloud')), 'directory of home')
            os.environ['CLOUDSDK_CONFIG'] = '~/gcloud'
            is_ok(Pyjo.GCP.Config.new().config_dir, str(GCLOUD), 'directory with a tilde')
        finally:
            if home is not None:
                os.environ['HOME'] = home
        is_ok(Pyjo.GCP.Config.new(config_dir=str(tmp)).config_dir, str(tmp), 'directory of an argument')

with subtest('Configurations'):
    with environ():
        config = Pyjo.GCP.Config.new()
        is_ok(config.configuration, None, 'no configuration of the environment')
        is_ok(config.active_configuration(), 'dev', 'configuration of active_config')
        is_ok(config.get('core/project'), 'dev-project', 'property of the active configuration')
        is_ok(config.get('project'), 'dev-project', 'property of core')
        is_ok(
            config.get('auth/impersonate_service_account'),
            'reader@dev-project.iam.gserviceaccount.com',
            'property of a section',
        )
        is_ok(config.get('account'), None, 'no property')
        is_ok(config.get('account', 'default'), 'me@example.com', 'property of a configuration')
        is_ok(config.properties('default'), {'core': {'project': 'default-project', 'account': 'me@example.com'}})
        is_ok(config.properties('missing'), {}, 'no configuration')
        config.properties()['core']['project'] = 'changed'
        is_ok(config.get('project'), 'dev-project', 'properties are a copy')

    with environ(CLOUDSDK_ACTIVE_CONFIG_NAME='default'):
        is_ok(Pyjo.GCP.Config.new().active_configuration(), 'default', 'configuration of the environment')
        is_ok(Pyjo.GCP.Config.new().get('project'), 'default-project', 'property of its configuration')
        is_ok(Pyjo.GCP.Config.new(configuration='dev').get('project'), 'dev-project', 'configuration of an argument')

    with environ(CLOUDSDK_CORE_PROJECT='env-project', CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT='sa@example.com'):
        config = Pyjo.GCP.Config.new()
        is_ok(config.get('project'), 'env-project', 'property of the environment')
        is_ok(config.get('auth/impersonate_service_account'), 'sa@example.com', 'property of a section of it')
        is_ok(config.properties()['core']['project'], 'dev-project', 'properties without the environment')

    with environ(CLOUDSDK_CONFIG=str(tmp.child('empty'))):
        config = Pyjo.GCP.Config.new()
        is_ok(config.active_configuration(), 'default', 'default configuration without active_config')
        is_ok(config.get('project'), None, 'no properties without the directory')

    with environ(CLOUDSDK_CONFIG=str(tmp)):
        tmp.child('configurations').make_path().child('config_default').spew('project = none\n')
        throws_ok(
            lambda: Pyjo.GCP.Config.new().get('project'),
            re.compile(r'^Cannot parse the configuration of gcloud .*config_default'),
            'no section',
        )

with subtest('Projects'):
    with environ():
        config = Pyjo.GCP.Config.new()
        is_ok(config.project(), None, 'no project of the environment')
        is_ok(config.quota_project(), None, 'no quota project')

    with environ(GCLOUD_PROJECT='legacy-project'):
        is_ok(Pyjo.GCP.Config.new().project(), 'legacy-project', 'project of GCLOUD_PROJECT')

    with environ(GOOGLE_CLOUD_PROJECT='my-project', GCLOUD_PROJECT='legacy-project'):
        is_ok(Pyjo.GCP.Config.new().project(), 'my-project', 'project of GOOGLE_CLOUD_PROJECT')

    with environ(GOOGLE_CLOUD_QUOTA_PROJECT='quota-project'):
        is_ok(Pyjo.GCP.Config.new().quota_project(), 'quota-project', 'quota project of the environment')

with subtest('Endpoints'):
    with environ():
        config = Pyjo.GCP.Config.new()
        is_ok(config.universe_domain(), 'googleapis.com', 'universe of Google Cloud')
        is_ok(config.endpoint_url('storage'), 'https://storage.googleapis.com', 'endpoint of a service')
        is_ok(config.emulator_host('storage'), None, 'no emulator')

    with environ(GOOGLE_CLOUD_UNIVERSE_DOMAIN='example.goog'):
        is_ok(Pyjo.GCP.Config.new().endpoint_url('iam'), 'https://iam.example.goog', 'endpoint of a universe')

    with environ(STORAGE_EMULATOR_HOST='localhost:4443', FIRESTORE_EMULATOR_HOST='https://localhost:8080'):
        config = Pyjo.GCP.Config.new()
        is_ok(config.emulator_host('storage'), 'http://localhost:4443', 'emulator without a scheme')
        is_ok(config.endpoint_url('storage'), 'http://localhost:4443', 'endpoint of the emulator')
        is_ok(config.endpoint_url('firestore'), 'https://localhost:8080', 'emulator with a scheme')
        is_ok(config.endpoint_url('pubsub'), 'https://pubsub.googleapis.com', 'service without an emulator')

with subtest('Certificates of mTLS'):
    workload = tmp.child('certificate_config.json').spew(
        '{"cert_configs": {"workload": {"cert_path": "/certs/client.crt", "key_path": "/certs/client.key"}}}'
    )
    home = tmp.child('home')

    with environ(HOME=str(home)):
        config = Pyjo.GCP.Config.new()
        is_ok(config.certificate_config(), None, 'no configuration of the certificate')
        is_ok(
            (config.use_client_certificate(), config.client_certificate()), (False, None), 'no certificate of a client'
        )
        is_ok((config.use_mtls_endpoint(), config.is_mtls()), ('auto', False), 'no mTLS without a certificate')
        is_ok(config.endpoint_url('storage'), 'https://storage.googleapis.com', 'endpoint without mTLS')

    with environ(HOME=str(home), GOOGLE_API_CERTIFICATE_CONFIG=str(workload)):
        config = Pyjo.GCP.Config.new()
        is_ok(config.certificate_config(), str(workload), 'configuration of GOOGLE_API_CERTIFICATE_CONFIG')
        ok(config.use_client_certificate(), 'certificate of a client of the configuration of the workload')
        is_ok(config.client_certificate(), ('/certs/client.crt', '/certs/client.key'), 'files of the workload')
        is_ok(config.endpoint_url('storage'), 'https://storage.mtls.googleapis.com', 'endpoint of mTLS')
        workload.spew('{}')
        is_ok(config.client_certificate(), ('/certs/client.crt', '/certs/client.key'), 'configuration read once')
        workload.spew(
            '{"cert_configs": {"workload": {"cert_path": "/certs/client.crt", "key_path": "/certs/client.key"}}}'
        )

    with environ(HOME=str(home), GOOGLE_API_CERTIFICATE_CONFIG=str(tmp.child('empty.json').spew('{}'))):
        ok(not Pyjo.GCP.Config.new().use_client_certificate(), 'no certificate of a configuration without a workload')

    with environ(HOME=str(home), CLOUDSDK_CONTEXT_AWARE_CERTIFICATE_CONFIG_FILE_PATH=str(workload)):
        is_ok(Pyjo.GCP.Config.new().certificate_config(), str(workload),
              'configuration of CLOUDSDK_CONTEXT_AWARE_CERTIFICATE_CONFIG_FILE_PATH')  # fmt: skip

    home.child('.config', 'gcloud').make_path().child('certificate_config.json').spew(workload.slurp())
    with environ(HOME=str(home), GOOGLE_API_USE_CLIENT_CERTIFICATE='true'):
        config = Pyjo.GCP.Config.new()
        like_ok(
            config.certificate_config(),
            re.compile(r'home/\.config/gcloud/certificate_config\.json$'),
            'default configuration',
        )
        is_ok(
            config.client_certificate(),
            ('/certs/client.crt', '/certs/client.key'),
            'certificate of GOOGLE_API_USE_CLIENT_CERTIFICATE',
        )

    with environ(
        HOME=str(home), GOOGLE_API_CERTIFICATE_CONFIG=str(workload), GOOGLE_API_USE_CLIENT_CERTIFICATE='False'
    ):
        is_ok(
            Pyjo.GCP.Config.new().client_certificate(),
            None,
            'no certificate of GOOGLE_API_USE_CLIENT_CERTIFICATE false',
        )

    with environ(HOME=str(home), GOOGLE_API_USE_MTLS_ENDPOINT='Always'):
        config = Pyjo.GCP.Config.new()
        is_ok((config.use_mtls_endpoint(), config.is_mtls()), ('always', True), 'mTLS always')
        is_ok(config.endpoint_url('pubsub'), 'https://pubsub.mtls.googleapis.com', 'endpoint of mTLS always')

    with environ(HOME=str(home), GOOGLE_API_USE_MTLS_ENDPOINT='always', GOOGLE_CLOUD_UNIVERSE_DOMAIN='example.goog'):
        throws_ok(lambda: Pyjo.GCP.Config.new().endpoint_url('pubsub'),
                  re.compile(r'^No endpoint of mTLS of Google Cloud in the universe domain example\.goog'), 'no mTLS of another universe')  # fmt: skip

    with environ(HOME=str(home), GOOGLE_API_CERTIFICATE_CONFIG=str(workload), GOOGLE_API_USE_MTLS_ENDPOINT='never'):
        is_ok(Pyjo.GCP.Config.new().endpoint_url('storage'), 'https://storage.googleapis.com', 'mTLS never')

    with environ(HOME=str(home), GOOGLE_API_USE_MTLS_ENDPOINT='sometimes'):
        throws_ok(lambda: Pyjo.GCP.Config.new().use_mtls_endpoint(),
                  re.compile(r"^Invalid GOOGLE_API_USE_MTLS_ENDPOINT 'sometimes'"), 'invalid mode of mTLS')  # fmt: skip

    with environ(HOME=str(home), STORAGE_EMULATOR_HOST='localhost:4443', GOOGLE_API_USE_MTLS_ENDPOINT='always'):
        is_ok(Pyjo.GCP.Config.new().endpoint_url('storage'), 'http://localhost:4443', 'emulator over mTLS')

done_testing()
