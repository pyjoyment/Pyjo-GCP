# Agent Guide: Pyjo-GCP

## Overview

`Pyjo.GCP` calls the APIs of Google Cloud with `Pyjo.UserAgent` of
Pyjoyment, without an SDK, in a distribution of its own, as Pyjoyment has no
business with one cloud. It is for a program that needs a few calls of Google
Cloud and no dependency for them, not a replacement of the client libraries of
Google: what it has is what such a program needs, the credentials that the
client libraries find, the tokens of OAuth 2.0 that they exchange them for,
and a client of the JSON APIs, not the generated clients of every API. The
conventions are those of Pyjoyment: read its `AGENTS.md` in the checkout next
to this one, `../Pyjoyment/AGENTS.md`. The plan is in the issues of this
repository.

Pyjo-GCP is the counterpart of Pyjo-AWS, in the checkout next to this one,
`../Pyjo-AWS`, which is made the same way and is the model of its design: read
its `AGENTS.md` before a module of this one is written.

## The Reference

The reference is the behaviour of the client libraries of Google, as the AIPs
of authentication describe it, https://google.aip.dev/auth, so that a program
finds the credentials and the project that the gcloud CLI and the client
libraries find:

- AIP-4110, Application Default Credentials: the order of the credentials, of
  `GOOGLE_APPLICATION_CREDENTIALS`, of the file of
  `gcloud auth application-default login`, and of the metadata server,
- AIP-4111, Self-signed JWT, and AIP-4112, Service Account Keys: the keys of a
  service account, with a JWT of RS256 signed by the program itself or
  exchanged for a token,
- AIP-4113, gcloud CLI Integration: the configuration directory of gcloud,
  `CLOUDSDK_CONFIG`, and its file of the credentials,
- AIP-4115, Default Credentials For Google Cloud Virtual Environments: the
  metadata server of Compute Engine, GKE, Cloud Run and Cloud Functions,
- AIP-4117, External Account Credentials: Workload Identity Federation, the
  token of another identity provider exchanged with the STS of Google.

Where an AIP is silent, the reference is `google-auth` of Python,
https://github.com/googleapis/google-auth-library-python, as botocore is the
one of Pyjo-AWS: `google/auth/_default.py` for the order and the project,
`google/oauth2` and `google/auth` for each kind of credentials.

## The Model of Pyjo-AWS

The mechanisms of Pyjo-AWS are meant to be taken as they are, and changed only
where Google Cloud differs:

- `Pyjo.Steps` of Pyjoyment, which was `Pyjo.AWS.Steps`, the coroutine of
  the operations that `run` drives blocking and `run_p` non-blocking, so that
  a provider of credentials and a call of the client are written once for
  both modes,
- `Pyjo.AWS.Credentials.Provider` and `Pyjo.AWS.Credentials.Chain`: `fetch`
  as a coroutine of the steps, `None` of a provider that is not configured, an
  exception of one that is configured and fails, which ends the chain, and the
  credentials kept until `refresh` seconds before their expiration, which a
  burst of calls gets once,
- `Pyjo.AWS.Client`: the credentials resolved before the transaction starts,
  and the errors of the API as exceptions with their code, message and status,
- `Pyjo.AWS.ECDSA`: the package `cryptography` of an extra when it is
  installed, and Python otherwise, which is how the RS256 of the keys of a
  service account is meant to be signed, so that the distribution depends on
  nothing but Pyjoyment,
- the tests that serve the endpoints of the cloud with an application of
  Pyjoyment.Lite, in a process of its own where a provider has a user agent of
  its own, as `t/AWS_Credentials_Metadata.py`.

What differs is the authorization: Google Cloud takes a bearer token of OAuth
2.0 in `Authorization`, not a signature of each request, so the credentials of
Pyjo-GCP are a token with its expiration, and the client adds the header to
the request of the call before it starts. The JSON APIs of Google share one
protocol, with the error of `google.rpc.Status`, so the client needs one class
of a call, `Pyjo.GCP.Call`, not one of a protocol of each kind of API, as
Pyjo-AWS does.

Pyjo-GCP does not depend on Pyjo-AWS: a module that both need is copied,
until it has a place in Pyjoyment, as the steps have in `Pyjo.Steps`.

## The Configuration

`Pyjo.GCP.Config` reads what google-auth reads, and the files of gcloud that
google-auth leaves to gcloud itself. The configuration directory is the one of
`_cloud_sdk.get_config_path`: `CLOUDSDK_CONFIG`, `~/.config/gcloud`, or
`%APPDATA%\gcloud` on Windows, with the drive of `SystemDrive` without
`APPDATA`. An empty `GOOGLE_APPLICATION_CREDENTIALS` is none, as google-auth
compares it with `""`.

google-auth gets the project of gcloud by running `gcloud config get project`,
which is slow, and missing where gcloud is not installed. `Pyjo.GCP.Config`
reads the properties of gcloud instead, as gcloud does: the configuration of
`CLOUDSDK_ACTIVE_CONFIG_NAME`, of the file `active_config`, or `default`, its
file `configurations/config_<name>` in the syntax of INI, and the variable
`CLOUDSDK_<SECTION>_<NAME>` over a property, as `CLOUDSDK_CORE_PROJECT`. The
properties of the installation of gcloud, in its own directory, are left out.

The project is not one method, as it depends on the credentials that the chain
finds, in the order of `_default.default`: `GOOGLE_CLOUD_PROJECT` or
`GCLOUD_PROJECT` of `project()` over all, then the one of the file of the
credentials, as `project_id` of a service account, then `core/project` of
gcloud only for the file of `gcloud auth application-default login`, also when
`GOOGLE_APPLICATION_CREDENTIALS` names it, then the one of the metadata
server only for its credentials. `GOOGLE_CLOUD_QUOTA_PROJECT` of
`quota_project()` comes over `quota_project_id` of the file, as
`with_quota_project_from_environment` does.

The endpoint of a service is `https://<service>.<universe domain>`, or the
emulator of `<SERVICE>_EMULATOR_HOST`, as `STORAGE_EMULATOR_HOST` of the client
library of Cloud Storage, with `http://` before a host without a scheme, which
the client calls without a token. `api_endpoint_overrides` of gcloud is not
read: its URLs have the path of the version of the API, as
`https://storage.googleapis.com/storage/v1/`, which the calls of the client
have in their paths.

## The Steps

The providers of the credentials and the calls of the client are coroutines
of `Pyjo.Steps` of Pyjoyment: a `Request`, a `Command` and a `Sleep`, which
`run` drives blocking and `run_p` non-blocking. It was a copy of
`Pyjo.AWS.Steps` here, `Pyjo.GCP.Steps`, until it went to Pyjoyment
(pyjoyment/Pyjoyment#540), so a change of it is made in Pyjoyment, and its
mechanism is in its documentation and in the section The Steps of
`../Pyjo-AWS/AGENTS.md`.

The environment and the timeout of a `Command` are what the executable of an
external account needs, as `subprocess.run` of google-auth gives them, and a
killed process is an exception of the timeout, not its exit code.

## The Credentials

A provider of `Pyjo.GCP.Credentials.Provider` is the one of Pyjo-AWS: read
the section The Credentials of `../Pyjo-AWS/AGENTS.md` for `fetch` as a
coroutine of the steps, `None` of a provider that is not configured, the
exception of one that is configured, which ends the chain, and the promise
that a burst of calls shares. The credentials are an access token of OAuth
2.0, kept until `refresh` seconds before its expiration, 225 as
`REFRESH_THRESHOLD` of google-auth has it, 3 minutes and 45 seconds, and
`__repr__` has no token.

`Pyjo.GCP.Credentials.Chain` is the order of `_default.default` without App
Engine of the first generation: `Pyjo.GCP.Credentials.File` of
`GOOGLE_APPLICATION_CREDENTIALS`, whose file that does not exist is an error,
and of `gcloud auth application-default login`, whose file that does not
exist is not configured, then the metadata server. A file is the provider of
its `type`, which `provider_of` makes of its JSON object with the user agent
of the file, so that the provider of the source of an impersonated service
account is made the same way. The file applies the quota project of the
environment and the project of gcloud, and the chain the project of the
environment, both on a copy of the credentials of `copy`, so that a provider
keeps its own.

The token of an `authorized_user` has the scopes of the login: google-auth
sends no `scope` with the refresh token of the Application Default
Credentials, as `with_scopes_if_required` leaves the credentials of a user
as they are. The token endpoint is `token_uri` of the file, or
`https://oauth2.googleapis.com/token`, where google-auth always takes the
latter: gcloud writes no `token_uri`, so the endpoint is the same for its
files, and a test points its file to an application of its own.

The token endpoints of OAuth 2.0 answer the same way, the token endpoint of
Google, the STS of Google and the metadata server alike: `access_token` and
`expires_in`, or `error` and `error_description`, which `parse_token` of
`Pyjo.GCP.Credentials.Provider` reads for them all.

## The Metadata Server

`Pyjo.GCP.Credentials.Metadata` is `google/auth/compute_engine` of
google-auth, with its environment variables: the request that finds the
server goes to `GCE_METADATA_IP`, `169.254.169.254`, the others to
`GCE_METADATA_HOST` or `GCE_METADATA_ROOT`, `metadata.google.internal`, all
with `Metadata-Flavor: Google`, whose response to the first has it too.
Without it, the product of `/sys/class/dmi/id/product_name` of Linux,
`Google...`, finds the server, as a machine of Google Cloud whose server is
slow to answer. The provider finds the server once, as `is_on_gce` of
`_default.default` does once a process, and then gets the token, the email of
the service account, the project and the universe domain, the last three
once; a server without a universe domain is of `googleapis.com`.
`NO_GCE_CHECK` is `true` in any case, where google-auth takes only the
lower case.

The provider has a user agent of its own, of `GCE_METADATA_TIMEOUT`, 3
seconds, and no connections kept, and `GCE_METADATA_DETECT_RETRIES`, 3, is
its attempts, for the request that finds the server and for the others of a
status of 5xx or without a connection: read the section The Container and the
Instance Metadata of `../Pyjo-AWS/AGENTS.md` for why the chain does not give
it its own. A machine that is not of Google Cloud waits for the attempts once,
which the chain reaches without other credentials only, as google-auth does;
`NO_GCE_CHECK=true` skips it. The tests set it, as a runner of GitHub Actions
has the IMDS of Azure on `169.254.169.254`, and `t/GCP_Credentials_Metadata.py`
serves the server with an application of Pyjoyment.Lite in a process of its
own, as `t/AWS_Credentials_Metadata.py` of Pyjo-AWS does, with
`GCE_METADATA_HOST` and `GCE_METADATA_IP` of it.

The email of a service account is in the path as it is, with its `@`, as
google-auth formats it. The scopes of the chain go to the token as
`scopes`, joined with commas, as the client libraries of Google give their
default scopes.

## The Service Accounts

`Pyjo.GCP.Credentials.ServiceAccount` is `google/oauth2/service_account.py`
of google-auth. The grant of RFC 7523 posts a JWT of the email, the scopes
and the subject of the domain-wide delegation, of an hour, whose audience is
`https://oauth2.googleapis.com/token` also when `token_uri` of the key is
another endpoint, as google-auth has it, to `token_uri`. The self-signed JWT
of AIP-4111 is the token itself, with `iss` and `sub` of the email and the
scopes in `scope`, without `aud`, as `always_use_jwt_access` of google-auth
makes it with scopes: it is off by default, as google-auth has it, but for a
key of another universe domain than `googleapis.com`, which has no token
endpoint, and a subject takes the grant always.

`Pyjo.GCP.RSA` signs RS256 as `Pyjo.AWS.ECDSA` of Pyjo-AWS signs ES256: read
its section aws login of `../Pyjo-AWS/AGENTS.md` for the package
`cryptography` of the extra `cryptography` imported with `importlib`, and
Python otherwise. The padding of PKCS #1 v1.5 is not random, so both backends
make the same signature, which `t/GCP_RSA.py` compares with the one of
`cryptography` and `openssl dgst -verify` checks. The signature of Python is
of the CRT, checked with the public key before it is given, as a fault of the
CRT would give the primes away, and is not constant-time, of a key on the
machine that has it. Its parser of DER is the one of `Pyjo.AWS.ECDSA`, with
lengths of up to four bytes, as a key of 4096 bits needs two.

The key of the tests is in `t/lib/Key.py`, a helper that the harness skips,
as in Pyjoyment, as its numbers, of which the tests make the PEM: a PEM of a
private key in the repository is what a scanner of secrets reports. The
workflow Tests runs without `cryptography`, so its backend is checked with
`uv run --with cryptography` in development.

## The Impersonated Service Accounts

`Pyjo.GCP.Credentials.Impersonated` is `google/auth/impersonated_credentials.py`
of google-auth: the token of `generateAccessToken` of the IAM Service Account
Credentials API, with the credentials of its source, a provider that it awaits
with `steps`, so that the source keeps its token until its own expiration.
The request is a call of `Pyjo.GCP.Client` with the credentials of the source
given to it, which adds their token and quota project, as `apply` of
google-auth does, and whose `Pyjo.GCP.Error` the exception of the provider
keeps the message of. The endpoint is
`https://iamcredentials.<universe domain>` of the universe domain of the
source, as google-auth has it, or an `endpoint` of the provider, or the `url`
of `generateAccessToken` itself, `iam_endpoint_override` of google-auth, which
an external account gives it. A test gives a relative one, as an empty
endpoint of the client is the server of its user agent, not none.

A file of `impersonated_service_account` names the service account in
`service_account_impersonation_url`, of which google-auth takes the service
account only, between the last `/` and `:generateAccessToken`, and so does
the provider: unlike `token_uri` of `authorized_user`, the endpoint of the URL
is not used. Its source is a file of `authorized_user`, `service_account` or
`external_account_authorized_user` in `source_credentials`, of `provider_of`
of `Pyjo.GCP.Credentials.File`, whose service account has the scope of IAM,
`https://www.googleapis.com/auth/iam`, as `with_scopes` of google-auth gives
it, and another impersonated service account is not one. The scopes of the
file come under those of the provider of the file, which always has some,
where google-auth takes them over the default scopes of a client library.

The source of a provider made in code needs a scope that calls IAM, as
`cloud-platform`, the default one of the chain, and not the scopes of the
target: a token of the metadata server of those cannot impersonate. The
project of the credentials is the one of the source, which the credentials of
google-auth do not have, so that a program with the chain as the source gets
the project of the environment, and a file of gcloud gets `core/project` as
its source has none.

With a `subject`, of the domain-wide delegation, the token is the one of the
grant of RFC 7523, of the JWT that `signJwt` of the API signs, posted to
`https://oauth2.googleapis.com/token`, in the universe domain
`googleapis.com` only, as google-auth has it.

## The External Accounts

`Pyjo.GCP.Credentials.ExternalAccount` is `google/auth/external_account.py` of
google-auth, the base class of the kinds of the source of the subject token,
which a subclass gets in `subject_token`, a coroutine of the steps, as
`retrieve_subject_token` of google-auth:
`Pyjo.GCP.Credentials.IdentityPool` of `identity_pool.py`, of a file or a
URL, `Pyjo.GCP.Credentials.Pluggable` of `pluggable.py`, of an executable,
and `Pyjo.GCP.Credentials.AWS` of `aws.py`, of AWS. `provider_of` of `Pyjo.GCP.Credentials.File` tells the kind of
`external_account` as `_get_external_account_credentials` of `_default.py`
does: AWS of its `subject_token_type`, an executable of `executable` of
`credential_source`, an identity pool otherwise, of a file, a URL or a
`certificate` of X.509.

The `certificate` of `Pyjo.GCP.Credentials.IdentityPool` is the one of
`identity_pool.py` with `_mtls_helper.py`: the files of `cert_path` and
`key_path` of `cert_configs.workload` of the configuration of
`certificate_config_location`, or of `GOOGLE_API_CERTIFICATE_CONFIG`, of
`CLOUDSDK_CONTEXT_AWARE_CERTIFICATE_CONFIG_FILE_PATH`, or of
`~/.config/gcloud/certificate_config.json`, as it is, not of
`CLOUDSDK_CONFIG`, as google-auth has it, with the well-known files of Cloud
Run for the paths of its configuration that gcloud wrote before. The subject
token is the JSON array of the certificate and of the ones of
`trust_chain_path` after it, without the certificate itself at the top of the
chain, in Base64 of their DER, which is the Base64 of the PEM without its
lines, so that no parser of X.509 is needed; the JSON is written as it is, as
`Pyjo.JSON` would write the slashes of Base64 as `\/`.

The requests of the provider present the certificate with the key of the
workload, of mTLS, as `functools.partial(request, cert=...)` of google-auth
does for the exchange and the impersonation, with a user agent of its own,
as `Pyjo.UserAgent` has its certificate for all its requests: the one of the
argument gives it its authority and its checks only. It keeps no connections,
as the one of `Pyjo.GCP.Credentials.Metadata`: nothing closes it, as
`Pyjo.GCP.Credentials.File` makes a new provider for each token, so a
connection that it kept would be a socket of TLS that is not closed, which
the workflow Tests found as a `ResourceWarning` of Python 3.14.
`t/GCP_Credentials_X509.py` serves the STS over TLS in a process of its own,
with the certificates of the package of Pyjoyment, `Pyjo/IOLoop/certs`:
`server.crt` of the server, which takes the requests with `client.crt` only,
the certificate of the workload, as `ca.crt` signs both, and the user agent of
the test takes it as its authority. `server.crt` is of `serverAuth` only,
which a server does not take of a client, so the certificate of a client
comes from Pyjoyment since `6aa1e72` of `uv.lock`, and no certificate of the
tests is in the repository.

The exchange is the one of `sts.py` and RFC 8693: the form of `grant_type`,
`audience`, `scope`, `requested_token_type`, `subject_token` and
`subject_token_type`, with `options` of `userProject` of a workforce pool
without a client, and the basic authentication of `client_id`, to
`token_url`, `https://sts.<universe domain>/v1/token` by default. Its
response and its error are those of OAuth 2.0, which `parse_token` reads,
with `expires_in` as a string too.

With `service_account_impersonation_url`, the token is the one of
`Pyjo.GCP.Credentials.Impersonated`, made once, with the URL as its `url`,
as google-auth calls the URL itself, and `token_lifetime_seconds` of
`service_account_impersonation` as its lifetime. Its source is a provider of
the federated token of the scope of IAM, as `with_scopes` of the impersonated
credentials of google-auth gives it, so that it keeps the federated token
until its expiration, not the external account itself, which would ask
itself again.

The executable of `Pyjo.GCP.Credentials.Pluggable` runs only with
`GOOGLE_EXTERNAL_ACCOUNT_ALLOW_EXECUTABLES=1`, with the command split as
`shlex.split` does, the environment of the process with the variables
`GOOGLE_EXTERNAL_ACCOUNT_*` of google-auth, and `timeout_millis` of 5 to 120
seconds, 30 by default. Its output is the JSON object of version 1 on its
standard output, or in `output_file` with none, whose token of
`expiration_time` that has not expired is taken without running it. An
output file of an invalid format is an error, as in google-auth, but one of a
token that is not valid, as an expired one, runs the executable. The
interactive mode of gcloud, and its revocation, are not supported, as
google-auth gives them only to gcloud.

The subject token of `Pyjo.GCP.Credentials.AWS` is a request of
`GetCallerIdentity` of `regional_cred_verification_url`, signed and not
sent, which the STS of Google sends to AWS: the percent-encoded JSON object
of its URL, its method and its headers. The credentials of AWS are those of
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN`, or of
the role of the instance metadata of `url` of the file, and the region is the
one of `AWS_REGION` or `AWS_DEFAULT_REGION`, or of the availability zone of
`region_url` without its last letter, with the session token of IMDSv2 of
`imdsv2_session_token_url` when the file has one, as google-auth has them.
That is all that google-auth reads, so the provider does not need the chain
of Pyjo-AWS, with its profiles, SSO and roles, and Pyjo-GCP does not depend
on Pyjo-AWS.

Its signature is `sign`, `RequestSigner` of google-auth, not a copy of
`Pyjo.AWS.SigV4`: a request with an empty body, of which `host`,
`x-amz-date` and `x-amz-security-token` are signed, and
`x-goog-cloud-target-resource` of the audience is added after the signature,
unsigned, as google-auth does. Its headers are the ones of google-auth for
the same time, which a check in development compares with google-auth
itself. The JSON object of the request has `\/` of `Pyjo.JSON` where the one
of google-auth has `/`, which is the same JSON for the STS of Google.

The project is the one of `get_project_id`, which `_default.py` asks for an
external account always: Cloud Resource Manager of the number of the project
of the audience, or of the workforce pool user project, with the token of the
provider, once, and none of a response that is not successful. Its URL is
`project_url`, of `googleapis.com` in any universe, as google-auth has it,
which a test points to its own application.

`Pyjo.GCP.Credentials.ExternalAccountAuthorizedUser` is
`external_account_authorized_user.py`: the refresh token of a user of a
workforce pool, with the basic authentication of its client, to `token_url`,
without scopes. The token of the file, with `expiry`, is the cached one of
the provider, as google-auth takes it as valid, and a file without the
fields of the refresh has that one only.

## The Agent Identities

`Pyjo.GCP.X509` is `_agent_identity_utils.py` of google-auth without the
package `cryptography`: the DER of a certificate of PEM, the fingerprint of
SHA-256 of its DER in Base64 without its padding, percent-encoded but its
slashes, as `quote` of google-auth makes it, and the URIs of its
subjectAltName, of a reader of DER of its own, as the one of `Pyjo.GCP.RSA`,
which walks the certificate to its extensions only. A certificate is of an
agent identity of a URI of SPIFFE of the trust domains
`agents.global.org-<n>.system.id.goog` and `agents.global.proj-<n>.system.id.goog`.

A token of such a certificate is bound to it, unless
`GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES` is `false`: the one
of the metadata server with `bindCertificateFingerprint` of the certificate
of the workload of `GOOGLE_API_CERTIFICATE_CONFIG`, or of the well-known one
of Cloud Run, and the one of the exchange of an external account of a
certificate with `bindCertFingerprint` of `options`, of `exchange_options` of
`Pyjo.GCP.Credentials.IdentityPool`, of its own certificate. The fingerprint
goes in the query or the form percent-encoded once more, as google-auth sends
it. A bound token is for the calls of mTLS with that certificate, which
`Pyjo.GCP.Client` makes of the same configuration, as
`GOOGLE_API_CERTIFICATE_CONFIG` turns its certificate on.

google-auth waits 30 seconds for the certificate of a configuration of
`GOOGLE_API_CERTIFICATE_CONFIG` that is not there yet, as of an agent that
starts before its certificate is written, and fails then; `agent_fingerprint`
fails at once, as a function and not a coroutine of the steps, whose `Sleep`
would wait without blocking the loop, and the provider gets the token again
on the next call.

`t/GCP_X509.py` checks the DER, the fingerprint and the URIs with the parser
of the module `ssl` of Python, and the tests of the agents take a
certificate of `Key.certificate` of `t/lib/Key.py`, made of the key of the
tests when they run, as Pyjoyment has no certificate of an agent: a server of
TLS of a test takes it as an authority of its own too.

## The Client

`Pyjo.GCP.Client` is the one of Pyjo-AWS: read the section The Client of
`../Pyjo-AWS/AGENTS.md` for the call as an object that builds its
transaction and reads its result, `steps` that a provider of credentials
awaits, and the credentials of `credentials_p` that calls at once share.
`t/GCP_Client.py` takes a relative endpoint for the same reason.

The token goes into the headers of the request when the call has built it,
not in the event `start` of the user agent, where Pyjo-AWS signs its request:
a signature needs the complete request, with its absolute URL, and a bearer
token does not. `x-goog-user-project` of the quota project goes with it, as
`apply` of the credentials of google-auth adds it, or the one of
`quota_project` of the client, `client_options.quota_project_id` of
google-api-core, or none of `False`. Cloud Storage bills a request with it to
that project, as one of a bucket of requester pays, and gives its response
`Cache-Control: no-cache, no-store` of its own then, over the one of the
metadata of the object, which a server of the objects of its own bucket, as
`examples/gcs.py`, does not want, so it takes `False`.

The endpoint is `https://<service>.<universe domain>` of `Pyjo.GCP.Config`,
or its emulator, which makes the client `anonymous`, as the client library
of Cloud Storage calls `STORAGE_EMULATOR_HOST` without credentials; an
`endpoint` of the client is neither, as a server of a test that checks the
token. Credentials of another universe domain than the one of the
configuration are an error, as `_validate_universe_domain` of
google-api-core has it, but for an `endpoint` of the client.

The mTLS of the client is the one of `configure_mtls_channel` of
google-auth and of the endpoints of google-api-core: the certificate of the
workload of the configuration of the certificate, which `Pyjo.GCP.Config`
reads, as `IdentityPool` does, with `GOOGLE_API_USE_CLIENT_CERTIFICATE=true`,
or without it when `GOOGLE_API_CERTIFICATE_CONFIG` names a configuration
with a workload, as `check_use_client_cert` has it, and the endpoint
`https://<service>.mtls.googleapis.com` of `GOOGLE_API_USE_MTLS_ENDPOINT`,
`auto` for a client with a certificate, `always` or `never`, in
`googleapis.com` only. The client gives the certificate to its user agent,
as `Pyjo.UserAgent` has it for all its requests, unless the user agent has
one of its own, and not for an emulator. `Config` reads a configuration of
the certificate once, as `endpoint_url` asks it for each call. The
certificate of `cert_provider_command` of the context-aware metadata of
Endpoint Verification is not read: it is a program that prints the key,
which `Pyjo.UserAgent` takes of a file only.

`Pyjo.GCP.Call` reads the error of the older format too, of Cloud Storage and
the APIs of the discovery documents, without `status` and with `errors`,
whose `reason` it takes, or the one of `google.rpc.ErrorInfo` of `details`.
The code of `Pyjo.GCP.Error` is the status of HTTP, as `error.code` of the
JSON APIs is, not the `google.rpc.Code` of gRPC. A name of an object of Cloud
Storage is one segment of the path of the JSON API, with its slashes
percent-encoded, which the router of Pyjoyment decodes, so the route of an
object in a test is a wildcard, `<*name>`.

## The Examples

`examples/` has the scripts that show what the distribution is for, a few
calls of Google Cloud with the Application Default Credentials of any kind,
as `examples/` of Pyjo-AWS has them, and `docs/examples.rst` includes them.
`examples/gcs.py` is the counterpart of `examples/s3.py` of Pyjo-AWS: the
same application, with `Pyjo.GCP.Client` and no client library of Google,
and the options of the gcloud CLI, `--bucket`, `--impersonate-service-account`
and `--emulator-host`.

The list of a folder is `objects.list` of the JSON API, and the content of
an object the media of the XML API, `/<bucket>/<name>`, with the slashes of
the name as they are, not `objects.get` of the JSON API with `alt=media`:
that one gives `Content-Disposition: attachment` of its own to an object
without one, which a browser downloads then instead of showing it, where the
XML API gives the headers of the metadata of the object, as S3 does. The
error of the XML API is XML, which `Pyjo.GCP.Call` does not read, so the
example has its status only, which is all that it needs, as `404`.

The client of the example takes `quota_project=False`: Cloud Storage gives
`Cache-Control: no-cache, no-store` of its own to a request with
`x-goog-user-project`, which the credentials of
`gcloud auth application-default login` have of their `quota_project_id`,
over `Cache-Control` of the metadata of the object, so that nothing that the
example serves would be kept by a browser or a CDN. Both were found with a
real bucket, and are what the example is for.

The content goes to the client as it comes, of `GetObject`, a subclass of
`Pyjo.GCP.Call` in the example, whose transaction forwards the chunks of a
response of `200` in the event `read` of its content, each one once the
client has read the one before, as `GetObject` of `examples/s3.py` does: read
the section The Examples of `../Pyjo-AWS/AGENTS.md` for the empty chunk,
the client that goes away and the client for each thread.

`t/examples/gcs.py` runs the example and Cloud Storage of its own in
processes of their own, as `t/examples/s3.py` of Pyjo-AWS, with
`--emulator-host`, as fake-gcs-server: the list of the JSON API, the media of
the XML API with the headers of the metadata, and no credentials, which the
emulator checks.

`examples/sendmail.py` is `sendmail` of the Gmail API, for `sendmail_path`
of PHP, cron and the others that pipe a message to it. It reads its options
by hand, not with `Pyjo.GetOpt`, which would take `-i` of PHP for an
abbreviation of `--impersonate-service-account`, and ignores the options of
sendmail that it has no use for, as `-odi` and `-v`. The message goes as it
comes, with CRLF of RFC 5322 for the LF of PHP, to the media upload of
`messages.send`, `message/rfc822` of up to 35 MB, which `SendMessage`, a
subclass of `Pyjo.GCP.Call`, sends as its body, where `raw` of JSON in
base64 would make it larger. Gmail sends to the recipients of To, Cc and Bcc
of the message, and has no envelope of its own, so the recipients of the
arguments that the headers do not have go to a Bcc that the example adds, and
those of the headers get the message also without `-t`, unlike sendmail.

Its exit code is the one of `sysexits.h`, of which `mail()` of PHP returns
`false`, but not `EX_TEMPFAIL`: PHP takes it for a message that sendmail
keeps to send later, and returns `true`, which a check with PHP found, so an
error of the API that may pass is `EX_UNAVAILABLE` too, as the example keeps
no message. `mail()` of PHP replaces the bytes of `0x80` to `0x9f` of a
subject with spaces, which breaks one of UTF-8 that is not encoded, so the
README of the examples tells PHP to encode it, as RFC 2047 needs anyway.

The Gmail API sends as a user: the subject of the domain-wide delegation of
a service account, of `signJwt` of an impersonated one without a key, or of
its key, whose provider of `Pyjo.GCP.Credentials.File` the example gives the
subject, as google-auth has `with_subject`, or the user of
`gcloud auth application-default login` with the scope of Gmail.
With `-bd` of sendmail, the example is an SMTP server of RFC 5321 on
`Pyjo.IOLoop.server`, a session of each connection, whose message goes to
the Gmail API with `call_p` in the event loop of the server, and whose reply
waits for the one of the API. The commands that the client sends before the
reply, as PIPELINING lets it, stay in the buffer until the message is sent,
so that their replies come in their order. The envelope of `MAIL FROM` and
`RCPT TO` goes to the From and the Bcc of `complete`, as `-f` and the
recipients of the arguments do. A temporary error of the API, of `429`, a
status of `5xx` or a connection, is `451`, which the client tries again, as
the server keeps no queue, and the others `550` and `554`. The server has no
AUTH and no STARTTLS, so it listens on the loopback by default, and stops of
`SIGINT` and `SIGTERM`, with the exit code `0` that `t/examples/sendmail.py`
checks. A socket pair of `signal.set_wakeup_fd` wakes its event loop up on a
signal, as `Pyjo.Server.Daemon` does: Python repeats a `select` that a signal
interrupts, so a server without connections, whose loop has no timer, would
not see `stop` of the handler of the signal, which a check of the time of the
stop found.

`t/examples/sendmail.py` runs it against the Gmail API of its own of
`GMAIL_EMULATOR_HOST`, which `<SERVICE>_EMULATOR_HOST` of `Pyjo.GCP.Config`
gives any service, without credentials.

## Imports of the Package

The modules of the distribution import the package and each other relatively,
`from .. import GCP` and `from . import Config`, not as `import Pyjo.GCP.Config`:
pyright takes `Pyjo` for the regular package of Pyjoyment in `.venv`, which
hides the namespace that `extend_path` keeps open, so it does not find
`Pyjo.GCP` of the checkout. The tests and the documentation import them as
`Pyjo.GCP.Config`, which Python finds through `extend_path`. A module of
Pyjoyment, as `Pyjo.Steps`, is imported as it is, `import Pyjo.Steps`.

The package and the tests take what Pyjoyment has, as the distribution depends
on it already and is a dogfood of it: the files of `Pyjo.File`, as `slurp` and
`child`, the hashes and Base64 of `Pyjo.Util`, as `sha256_sum` and
`b64url_encode`, the JSON of `Pyjo.JSON`, and the times of RFC 3339 of
`Pyjo.Date`, not `open`, `os.path`, `hashlib`, `base64` and the formats of
`datetime`. What Pyjoyment lacks and the distribution needs is added to
Pyjoyment, not written here, as a release of Pyjoyment comes first anyway.

## Security

The files of secrets of Pyjoyment are git-ignored in `.gitignore` and denied to
Claude Code in `.claude/settings.json`, and so are the credentials of gcloud on
the machine, `application_default_credentials.json`, `credentials.db`,
`access_tokens.db` and `legacy_credentials` of `~/.config/gcloud`. A key of a
service account has no name of its own, so a file of one that is not in the
repository is not denied by a rule, and is never read. A test never reads the
files of the machine: it sets `GOOGLE_APPLICATION_CREDENTIALS`,
`CLOUDSDK_CONFIG` and `HOME` to files of its own, with a key made for the
test, and serves the endpoints of Google that it needs with an application of
Pyjoyment, with `NO_GCE_CHECK` or `GCE_METADATA_HOST` of its own, so that no
test asks the metadata server of the machine.

## Development

The distribution depends on the release of Pyjoyment on PyPI, with the lowest
version that has what it uses, which `uv.lock` pins. A change of Pyjoyment that
is not released yet would be its Git repository in `[tool.uv.sources]` of
`pyproject.toml`, until its release, and not a path to the checkout next to
this one: uv applies the sources of a dependency of Git, so whoever installs
the distribution from Git would get a subdirectory of this repository that
does not exist. The lowest version is then the one of Git, as `0.2.1.dev1`,
which PyPI does not have, so that an installation of PyPI fails to resolve it
rather than to import what the release has not, and the workflow Build
installs the wheel with the Pyjoyment of `uv.lock`, of `uv export`, as the
wheel does not name the source. The tests lay the checkout next to this one
over it with
`--with-editable`, so that they test what is there:

```sh
mise exec -- uv sync
mise exec -- uv run --with-editable ../Pyjoyment python -m Pyjo.Prove -l -r t
```

Perl's `prove` runs them too, with `.proverc`, under `uv run`, whose `python`
is the one of the environment, where Pyjoyment and the distribution are
installed, so that it needs no `PYTHONPATH`, unlike in Pyjoyment:

```sh
mise exec -- uv run --with-editable ../Pyjoyment prove -r t
```

The package is in the namespace `Pyjo` of Pyjoyment, which `extend_path` keeps
open, but it changes nothing of Pyjoyment, so the suite of Pyjoyment is not
run with it installed, unlike the one of a distribution of a reactor, which
runs on the reactor. What the distribution could break is the namespace, with
an `__init__.py` of `Pyjo` of its own, which the workflow Build checks.

The workflow Tests runs the tests of the distribution against the release of
`uv.lock`, without `--with-editable`, so that a pull request tests what an
installation gets. A dispatch with `pyjoyment-ref` lays a checkout of the ref
over it, as in development, so that what the next release of Pyjoyment breaks
is known before the release.

Trunk checks the files with the linters of Pyjoyment, from `.trunk/trunk.yaml`:

```sh
trunk check --all
```

actionlint is the one of the maintained fork kjanat/actionlint, whose releases
continue those of rhysd/actionlint after 1.7.12, as in Pyjoyment: `downloads`
in `.trunk/trunk.yaml` replaces the URLs of the plugin with those of the fork,
whose files have the same names.

Biome formats and lints JSON, Markdown and YAML, with `biome.jsonc`, in the
place of prettier, markdownlint and yamlfmt, as in Pyjoyment, and yamllint
checks what Biome does not, as the duplicated keys. The version of Biome is
the pinned one of `.trunk/trunk.yaml`, where `!` keeps it from
`trunk upgrade`, and which Renovate bumps, as in the repositories of
freelensapp: the repository has no `package.json` of its own. Renovate cannot
run `biome migrate`, so the workflow Biome Migrate runs it with
`npx --yes @biomejs/biome@<version>` of that version, migrates `biome.jsonc` on
the branch of Renovate and commits it with the token of the workflow, as the
author that `gitIgnoredAuthors` of `.renovaterc.json` names, so that Renovate
keeps updating the branch, and starts the checks of the commit with
`workflow_dispatch`; anywhere else, a `biome.jsonc` that this Biome would
migrate fails the check. The definition of Biome in `.trunk/trunk.yaml` is
the one of Pyjoyment, which explains why it is not the one of the plugin of
Trunk.

Its pyright needs the environment of `uv sync`, `.venv`, which `tool.pyright` of
`pyproject.toml` names, as the package imports Pyjoyment; Trunk Check of CI
runs `uv sync` first. The tests and `docs/conf.py` are not checked by pyright:
for them it takes the regular package `Pyjo` of Pyjoyment, which hides
`Pyjo.GCP` of the checkout.

The wheel has only the package `Pyjo.GCP` (`only-include` of hatchling), not
the `__init__.py` of `Pyjo`, which is the one of Pyjoyment; the workflow Build
checks it.

The documentation is on Read the Docs, a subproject of the one of Pyjoyment:
the docstrings of the package, which autodoc imports, as in Pyjoyment. Read the
Docs installs it with `uv sync` of `uv.lock` and the group `docs`, not with pip
and a `docs/requirements.txt` as Pyjoyment does, so that it builds with the
versions of the lock, as the workflow Docs does. The links to the
modules of Pyjoyment come from intersphinx. The workflow Docs builds it with
`-W`, as Read the Docs does, with the Pyjoyment of `uv.lock`:

```sh
mise exec -- uv run --group docs --with-editable ../Pyjoyment sphinx-build -W --keep-going -b html docs docs/_build/html
```

The workflow Tests ends with the job `Tests`, the one check of it that the
ruleset of `main` requires, as in Pyjoyment: it fails when a job of the
matrix failed or was cancelled, so a new version of Python needs no change of
the ruleset.

## Releases

The releases are those of Pyjoyment, with its workflows: a release is a tag of
the version of `pyproject.toml`, without a `v`, as `0.1.0`, which Automated
version sets with `uv version`, the components of its `--bump` from a list, as
`patch dev` or `minor rc`, or the version of `manual`, in the pull request of
the branch `automated/version`. After a release, a pre-release goes with the
release that it comes before, as PEP 440 orders `0.2.0.dev1` before `0.2.0`,
so `dev` alone after `0.2.0` fails. Automated tag tags the merge commit of that pull
request when it is merged, or with a comment `/tag` of a maintainer on it, and
starts Release on the tag. A development version, as `0.1.1.dev1`, is not
tagged. The version is static in `pyproject.toml`, as `uv version` cannot set a
dynamic one, and `__version__` of the package reads it from the metadata of
the distribution.

Release builds the sdist and the wheel, attests their build provenance with
`actions/attest`, and makes a draft of the GitHub release with them, whose
notes are rewritten before it is published, and an SBOM in SPDX, attested
with them. The package bundles nothing, unlike the one of Pyjoyment, whose SBOM
lists the JavaScript libraries of its package, so the SBOM is what an
installation of the wheel gets: the distribution and its dependencies at the
versions of `uv.lock`, installed in a virtual environment of their own, which
Syft scans. Syft on `uv.lock` itself would take its dependency groups too, as
Sphinx, which an installation does not get. The sdist does not
carry the SBOM, as the one of Pyjoyment does, as it is made of the wheel,
which is built after the sdist.

The workflow PyPI, run manually, publishes the files of the latest published
release, or of the release of the tag of its input, on PyPI once their
attestations of Release verify, in the environment `publishing`, which waits
for an approval and takes `main` and tags only. The trusted publisher of PyPI
names `pypi.yaml` and that environment.

```sh
gh attestation verify pyjo_gcp-0.1.0.tar.gz -R pyjoyment/Pyjo-GCP
```
