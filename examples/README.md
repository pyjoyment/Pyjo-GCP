# Examples

Short scripts that show what Pyjo-GCP does, with the Application Default
Credentials that the client libraries of Google find, of any kind: the key of
a service account of `GOOGLE_APPLICATION_CREDENTIALS`, the credentials of
`gcloud auth application-default login`, Workload Identity Federation, or the
metadata server of Compute Engine, GKE or Cloud Run.

## Layout

| Script   | What it does                                                                    |
| -------- | ------------------------------------------------------------------------------- |
| `gcs.py` | serves a bucket of Cloud Storage as a website, an application of Pyjoyment.Lite |

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
