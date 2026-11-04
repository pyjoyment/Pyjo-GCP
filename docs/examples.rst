Examples
========

The scripts of the directory ``examples`` of the repository, with the
Application Default Credentials that the client libraries of Google find, of
any kind, as :mod:`Pyjo.GCP.Credentials.Chain` finds them.


Cloud Storage
-------------

A bucket of Cloud Storage as a website, with :mod:`Pyjo.GCP.Client` and the
calls of :mod:`Pyjo.GCP.Call`, whose requests the actions await in the event
loop of the server, without a client library of Google: the content of an
object, as it comes, of a call that forwards it to the client, with the
headers of its metadata, ``index.html`` of a folder, or the list of its
folders and objects. ::

    uv run python examples/gcs.py --bucket mybucket daemon

.. include:: ../examples/gcs.py
   :code: python


Gmail
-----

A message of the standard input sent with the Gmail API, in the place of
``sendmail``, with its options that PHP, cron and the others give it, as the
user of the credentials, or the subject of the domain-wide delegation of a
service account, of a key or impersonated without one, and a call of
:mod:`Pyjo.GCP.Call` whose request has the message itself, of the media
upload of ``messages.send``. ::

    uv run python examples/sendmail.py --subject noreply@example.com -t -i < message.eml

.. include:: ../examples/sendmail.py
   :code: python
