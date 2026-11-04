# Examples

Short scripts that show what Pyjo-GCP does, with the Application Default
Credentials that the client libraries of Google find, of any kind: the key of
a service account of `GOOGLE_APPLICATION_CREDENTIALS`, the credentials of
`gcloud auth application-default login`, Workload Identity Federation, or the
metadata server of Compute Engine, GKE or Cloud Run.

## Layout

| Script        | What it does                                                                         |
| ------------- | ------------------------------------------------------------------------------------ |
| `gcs.py`      | serves a bucket of Cloud Storage as a website, an application of Pyjoyment.Lite      |
| `sendmail.py` | sends a message of the standard input with the Gmail API, in the place of `sendmail` |

## Running

Run the scripts from the root of the repository with `uv run`, which runs them
with Pyjo-GCP of the checkout, and without a client library of Google.

The application of `gcs.py` serves a bucket of Cloud Storage as a website:
the content of an object, as it comes, `index.html` of a folder, or the list
of its folders and objects. Its options before the command have the names of
the gcloud CLI, `--bucket` and `--impersonate-service-account`, and
`--emulator-host`, or the environment variables `GCS_BUCKET`,
`CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT` and `STORAGE_EMULATOR_HOST` in
their place:

```sh
uv run python examples/gcs.py --bucket mybucket daemon
```

The credentials of the user need `gcloud auth application-default login`
first. A service account, which the credentials impersonate, needs the role
Service Account Token Creator of the user on it:

```sh
uv run python examples/gcs.py --impersonate-service-account reader@myproject.iam.gserviceaccount.com --bucket mybucket daemon
```

An emulator, as fake-gcs-server, takes no credentials:

```sh
uv run python examples/gcs.py --emulator-host localhost:4443 --bucket mybucket daemon
```

## sendmail

`sendmail.py` reads a message from its standard input and sends it with the
Gmail API, as the user of the credentials, in the place of `sendmail`, with
its options that PHP, cron and the others give it: `-t` for the recipients of
the headers, `-i` or `-oi` for a line of a dot that does not end the
message, `-f` and `-F` for the sender, and the recipients as arguments. Its
exit code is the one of sendmail, so that `mail()` of PHP returns `false` for
a message that is not sent.

The Gmail API sends as a user, so the credentials need the scope
`https://www.googleapis.com/auth/gmail.send` of one. In Google Workspace, a
service account with the domain-wide delegation of that scope sends as any
user of the domain, `--subject`, or the environment variable
`GMAIL_SUBJECT`. With `--impersonate-service-account`, the Application
Default Credentials impersonate it without a key, and need the role Service
Account Token Creator on it:

```sh
uv run python examples/sendmail.py --impersonate-service-account mailer@myproject.iam.gserviceaccount.com \
  --subject noreply@example.com -t -i < message.eml
```

or with the key of the service account of `GOOGLE_APPLICATION_CREDENTIALS`:

```sh
GOOGLE_APPLICATION_CREDENTIALS=mailer.json uv run python examples/sendmail.py --subject noreply@example.com -t -i < message.eml
```

A user of Gmail sends as itself, with the credentials of
`gcloud auth application-default login` that have the scope of Gmail, which
needs an OAuth client of its own, `--client-id-file`:

```sh
gcloud auth application-default login --client-id-file=client.json \
  --scopes=https://www.googleapis.com/auth/gmail.send,https://www.googleapis.com/auth/cloud-platform
uv run python examples/sendmail.py -t -i < message.eml
```

In `php.ini`, the options go after the script, with the Python that has
Pyjo-GCP installed:

```ini
sendmail_path = "/opt/pyjo/bin/python /opt/pyjo/examples/sendmail.py --impersonate-service-account mailer@myproject.iam.gserviceaccount.com --subject noreply@example.com -t -i"
```

The headers of the message are as they come, so a subject of PHP that is not
ASCII is `mb_encode_mimeheader()` of it, which `mail()` needs anyway.

With `-bd` of sendmail, the script is an SMTP server, for the programs that
send with SMTP, as PHPMailer or Symfony Mailer of PHP, on `127.0.0.1:2525`
by default, or the address and the port of `--listen`. The envelope of
`MAIL FROM` and `RCPT TO` is the one of `-f` and of the recipients of the
arguments, and a message that the Gmail API does not take now is `451`, which
the client tries again:

```sh
uv run python examples/sendmail.py --impersonate-service-account mailer@myproject.iam.gserviceaccount.com \
  --subject noreply@example.com -bd --listen 127.0.0.1:2525
```

The server has no `AUTH` and no `STARTTLS`, so anyone who connects to it
sends as the subject: it listens on the loopback, or in a network of its own,
as a container next to the application.
