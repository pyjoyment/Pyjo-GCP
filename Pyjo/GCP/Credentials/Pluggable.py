"""
Pyjo.GCP.Credentials.Pluggable - Credentials of an external account of an executable
====================================================================================
::

    import os

    from Pyjo.GCP.Credentials.Pluggable import Pluggable

    os.environ['GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES'] = '1'

    provider = Pluggable(
        audience='//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/oidc',
        subject_token_type='urn:ietf:params:oauth:token-type:jwt',
        command='/opt/bin/oidc-token --audience pool',
        output_file='/var/cache/oidc-token.json',
    )
    print(provider.credentials().token)

:mod:`Pyjo.GCP.Credentials.Pluggable` is the provider of the credentials of
an external account whose subject token is the output of an executable, of a
file of the type ``external_account`` with ``executable`` of
``credential_source``, as
``gcloud iam workload-identity-pools create-cred-config --executable-command``
writes it: ::

    {
      "type": "external_account",
      "audience": "//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/oidc",
      "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
      "token_url": "https://sts.googleapis.com/v1/token",
      "credential_source": {
        "executable": {
          "command": "/opt/bin/oidc-token --audience pool",
          "timeout_millis": 5000,
          "output_file": "/var/cache/oidc-token.json"
        }
      }
    }

The executable runs only with ``GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES=1``
in the environment, as google-auth has it, with the variables
``GOOGLE_EXTERNAL_ACCOUNT_AUDIENCE``, ``GOOGLE_EXTERNAL_ACCOUNT_TOKEN_TYPE``,
``GOOGLE_EXTERNAL_ACCOUNT_ID``, ``GOOGLE_EXTERNAL_ACCOUNT_INTERACTIVE``,
``GOOGLE_EXTERNAL_ACCOUNT_IMPERSONATED_EMAIL`` and
``GOOGLE_EXTERNAL_ACCOUNT_OUTPUT_FILE``, and its output is a JSON object of
version 1: ::

    {
      "version": 1,
      "success": true,
      "token_type": "urn:ietf:params:oauth:token-type:jwt",
      "id_token": "eyJhbGciOiJSUzI1NiIs...",
      "expiration_time": 1762261200
    }

with ``id_token`` of the types of a JWT and an OIDC token, or
``saml_response`` of SAML 2.0, or ``"success": false`` with ``code`` and
``message``. A token of ``output_file`` that has not expired is taken without
running the executable. The interactive mode of gcloud is not supported.

See also
--------

:mod:`Pyjo.GCP.Credentials.ExternalAccount`,
:mod:`Pyjo.GCP.Credentials.File`, https://google.aip.dev/auth/4117,
https://cloud.google.com/iam/docs/workload-identity-federation-with-other-providers#executable-sourced-credentials.

Classes
-------
"""

import Pyjo.Date
import Pyjo.Exception
import Pyjo.File
import Pyjo.JSON

from Pyjo.Util import getenv

from . import ExternalAccount

import os
import shlex

from collections.abc import Mapping
from typing import Any, cast


TIMEOUT = 30
"""The number of seconds that the executable may run by default, 30."""

_TOKENS = {
    'urn:ietf:params:oauth:token-type:jwt': 'id_token',
    'urn:ietf:params:oauth:token-type:id_token': 'id_token',
    'urn:ietf:params:oauth:token-type:saml2': 'saml_response',
}


class Pyjo_GCP_Credentials_Pluggable(ExternalAccount.object):
    """
    :mod:`Pyjo.GCP.Credentials.Pluggable` inherits all attributes and
    methods from :mod:`Pyjo.GCP.Credentials.ExternalAccount` and implements
    the following new ones.
    """

    def __init__(
        self,
        *,
        command: str,
        timeout: float = TIMEOUT,
        output_file: str | None = None,
        **kwargs: Any,
    ) -> None:
        """::

            provider = Pyjo.GCP.Credentials.Pluggable.new(audience=audience, subject_token_type=token_type,
                                                          command='/opt/bin/oidc-token', timeout=5)

        Construct a new :mod:`Pyjo.GCP.Credentials.Pluggable` object, with
        the options of :mod:`Pyjo.GCP.Credentials.ExternalAccount`, or a
        :mod:`Pyjo.Exception` without a command, or of a timeout that is not
        of 5 to 120 seconds.
        """
        super().__init__(**kwargs)

        if not command:
            raise _invalid('no command of the executable of the credential_source')
        if not 5 <= timeout <= 120:
            raise _invalid(f'the timeout of the executable {timeout:g} seconds, not of 5 to 120')

        self.command = command
        """::

            command = provider.command

        The command of the executable, with its arguments, split as a shell
        does.
        """

        self.timeout = timeout
        """::

            seconds = provider.timeout

        The number of seconds that the executable may run, 30 by default,
        of 5 to 120.
        """

        self.output_file = output_file
        """::

            path = provider.output_file

        The file where the executable keeps its output, of a token that is
        taken until it expires, or ``None``.
        """

    @classmethod
    def options_of(cls, info: Mapping[str, Any]) -> dict[str, Any]:
        """::

            options = Pluggable.options_of(info)

        The options of ``executable`` of ``credential_source`` of the JSON
        object of a file: ``command``, ``timeout_millis`` and
        ``output_file``.
        """
        source = info.get('credential_source')
        value = cast(Mapping[str, Any], source).get('executable') if isinstance(source, Mapping) else None
        if not isinstance(value, Mapping):
            raise _invalid('no executable of the credential_source')
        executable = cast(Mapping[str, Any], value)
        millis = executable.get('timeout_millis')
        return {
            'command': executable.get('command') or '',
            'timeout': millis / 1000 if isinstance(millis, (int, float)) and millis else TIMEOUT,
            'output_file': executable.get('output_file'),
        }

    def environment(self) -> dict[str, str]:
        """::

            env = provider.environment()

        The environment of the executable, the one of the process with the
        variables of the external account.
        """
        env = dict(os.environ)
        env['GOOGLE_EXTERNAL_ACCOUNT_AUDIENCE'] = self.audience
        env['GOOGLE_EXTERNAL_ACCOUNT_TOKEN_TYPE'] = self.subject_token_type
        env['GOOGLE_EXTERNAL_ACCOUNT_ID'] = self.service_account() or ''
        env['GOOGLE_EXTERNAL_ACCOUNT_INTERACTIVE'] = '0'
        env['GOOGLE_EXTERNAL_ACCOUNT_REVOKE'] = '0'
        if self.service_account_impersonation_url is not None:
            env['GOOGLE_EXTERNAL_ACCOUNT_IMPERSONATED_EMAIL'] = self.service_account() or ''
        if self.output_file is not None:
            env['GOOGLE_EXTERNAL_ACCOUNT_OUTPUT_FILE'] = self.output_file
        return env

    async def subject_token(self) -> str:
        """::

            token = await provider.subject_token()

        The subject token of :attr:`output_file` that has not expired, or of
        the output of the executable, or a :mod:`Pyjo.Exception` without
        ``GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES=1``, of an executable
        that fails, or of an output without the token.
        """
        if getenv('GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES') != '1':
            raise Pyjo.Exception.new(
                'Cannot run the executable of an external account: GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES is not 1'
            )
        if self.output_file is not None and (token := self._cached(self.output_file)) is not None:
            return token
        code, out, err = await self.run(shlex.split(self.command), env=self.environment(), timeout=self.timeout)
        if code != 0:
            output = (out + err).decode(errors='replace').strip()
            raise Pyjo.Exception.new(f'Cannot run the executable of an external account: exit {code}: {output}')
        if not out.strip() and self.output_file is not None:
            out = Pyjo.File.path(self.output_file).slurp() or b''
        try:
            response: Any = Pyjo.JSON.decode_json(out)
        except ValueError:
            response = None
        if not isinstance(response, dict):
            raise _invalid('no JSON object of the output of the executable')
        return _token(cast(dict[str, Any], response))

    # The token of the output file, or None of a file that is not there, that is not a JSON object, or whose token is
    # not valid or has no expiration, as google-auth runs the executable then, but not of an invalid format
    def _cached(self, path: str) -> str | None:
        file = Pyjo.File.path(path)
        try:
            response: Any = Pyjo.JSON.decode_json(file.slurp() or b'') if file.is_file else None
        except ValueError:
            response = None
        if not isinstance(response, dict):
            return None
        response = cast(dict[str, Any], response)
        _schema(response)
        if 'expiration_time' not in response:
            return None
        try:
            return _token(response)
        except _Invalid:
            raise
        except Pyjo.Exception.object:
            return None


# An output of the executable of an invalid format, which google-auth raises also of the output file
class _Invalid(Pyjo.Exception.object):
    pass


def _invalid(reason: str) -> _Invalid:
    return _Invalid(f'Invalid credentials of an external account: {reason}')


def _schema(response: Mapping[str, Any]) -> None:
    for name in ('version', 'success'):
        if name not in response:
            raise _invalid(f'no {name} of the output of the executable')
    if not response['success'] and ('code' not in response or 'message' not in response):
        raise _invalid('no code or message of the output of the executable')


def _token(response: Mapping[str, Any]) -> str:
    _schema(response)
    version = response['version']
    if not isinstance(version, int) or version > 1:
        raise Pyjo.Exception.new(
            f'Unsupported version of the output of the executable of an external account: {version}'
        )
    if not response['success']:
        raise Pyjo.Exception.new(
            f'The executable of an external account failed: {response["code"]}: {response["message"]}'
        )
    expiration = response.get('expiration_time')
    if isinstance(expiration, (int, float)) and expiration < (Pyjo.Date.new().epoch or 0):
        raise Pyjo.Exception.new('The token of the executable of an external account has expired')
    if 'token_type' not in response:
        raise _invalid('no token_type of the output of the executable')
    if (field := _TOKENS.get(response['token_type'])) is None:
        raise Pyjo.Exception.new(
            f'Unsupported token_type of the output of the executable of an external account: {response["token_type"]}'
        )
    if not isinstance(token := response.get(field), str) or not token:
        raise _invalid(f'no {field} of the output of the executable')
    return token


new = Pyjo_GCP_Credentials_Pluggable.new
object = Pyjo_GCP_Credentials_Pluggable
Pluggable = Pyjo_GCP_Credentials_Pluggable
