"""
Pyjo.GCP.Call - Call of a JSON API of Google Cloud
==================================================
::

    from Pyjo.GCP.Call import Call
    from Pyjo.GCP.Client import Client

    buckets = Client(service='storage').call(Call('GET', '/storage/v1/b', query={'project': 'myproject'}))
    print([bucket['name'] for bucket in buckets.get('items', [])])

    # Or import the module, as in Google Python Style Guide

    import Pyjo.GCP.Call
    import Pyjo.GCP.Client

    iam = Pyjo.GCP.Client.new(service='iamcredentials')
    call = Pyjo.GCP.Call.new(
        'POST',
        '/v1/projects/-/serviceAccounts/reader@myproject.iam.gserviceaccount.com:generateAccessToken',
        {'scope': ['https://www.googleapis.com/auth/cloud-platform']},
    )
    iam.call_p(call).then(lambda token: print(token['expireTime'])).wait()

:mod:`Pyjo.GCP.Call` is a call of a JSON API of Google Cloud, the one
protocol of the APIs of Google over HTTP and JSON: a method and a path,
which is percent-encoded already, with the parameters of its query, its
headers and the JSON of its body. The result is the JSON of the response,
its body of another type, or ``None`` without a body, and the error is the
:mod:`Pyjo.GCP.Error` of ``google.rpc.Status`` of the response. The media
of a request with ``alt=media``, as an object of Cloud Storage, is its body
of any type, also of JSON, as ``MediaModel`` of the client of the discovery
documents of Google has it: ::

    data = storage.call(Call('GET', '/storage/v1/b/mybucket/o/config.json', query={'alt': 'media'}))

Without the discovery documents of the APIs, which the client libraries of
Google are generated from, a call takes the names and the structure of the
API as its documentation has them, and gives the result as the response
has it. A subclass changes the transaction and the result, as a call of a
method that gives its body without ``alt=media``, as ``files.export`` of
Google Drive, or of the media of the XML API of Cloud Storage: ::

    class Export(Call):
        def __init__(self, file_id, mime_type):
            super().__init__('GET', f'/drive/v3/files/{file_id}/export', query={'mimeType': mime_type})

        def parse(self, tx):
            return tx.res.body

See also
--------

:mod:`Pyjo.GCP.Client`, :mod:`Pyjo.GCP.Error`, https://google.aip.dev/127.

Classes
-------
"""

import Pyjo.Base
import Pyjo.Transaction.HTTP
import Pyjo.URL
import Pyjo.UserAgent

from . import Error

from collections.abc import Mapping
from typing import Any, cast


class Pyjo_GCP_Call(Pyjo.Base.object):
    """
    :mod:`Pyjo.GCP.Call` inherits all attributes and methods from
    :mod:`Pyjo.Base` and implements the following new ones.
    """

    def __init__(
        self,
        method: str,
        path: str,
        json: Any = None,
        *,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """::

            call = Pyjo.GCP.Call.new('GET', '/storage/v1/b/mybucket/o', query={'prefix': 'docs/'})
            call = Pyjo.GCP.Call.new('POST', '/v1/projects/myproject/topics/mytopic:publish',
                                     {'messages': [{'data': 'SGVsbG8='}]})

        Construct a new :mod:`Pyjo.GCP.Call` object.
        """
        self.method = method
        """::

            method = call.method

        The method of the request, as ``GET``.
        """

        self.path = path
        """::

            path = call.path

        The path of the request, which is percent-encoded already, as
        ``/storage/v1/b/mybucket/o/docs%2Findex.html``, with the parameters
        of a query too.
        """

        self.json = json
        """::

            json = call.json

        The JSON of the body of the request, or ``None`` for none.
        """

        self.query = dict(query or {})
        """::

            query = call.query

        The parameters of the query, without those of ``None``, of strings,
        ``true`` or ``false`` of booleans, the strings of the others, and a
        parameter of each value of a list.
        """

        self.headers = dict(headers or {})
        """::

            headers = call.headers

        The headers of the request.
        """

    def build_tx(self, ua: Pyjo.UserAgent.object, url: Pyjo.URL.object) -> Pyjo.Transaction.HTTP.object:
        """::

            tx = call.build_tx(ua, Pyjo.URL.new('https://storage.googleapis.com'))

        The transaction of the method and the path, after the path of the
        endpoint, of a new :mod:`Pyjo.URL` object, which it may change, with
        the JSON of the body.
        """
        url = url_for(url, self.path, self.query)
        if self.json is None:
            return ua.build_tx(self.method, url, self.headers)
        return ua.build_tx(self.method, url, self.headers, json=self.json)

    def error(self, tx: Pyjo.Transaction.HTTP.object) -> Error.object:
        """::

            e = call.error(tx)

        The :mod:`Pyjo.GCP.Error` of a response with an error status, of the
        JSON of ``google.rpc.Status`` in ``error``, or of the status of the
        response without it.
        """
        res = tx.res
        try:
            data: Any = res.json() if res.body else None
        except ValueError:
            data = None
        fields: dict[str, Any] = {}
        if isinstance(data, dict) and isinstance(error := cast(dict[str, Any], data).get('error'), dict):
            fields = cast(dict[str, Any], error)
        code = fields.get('code')
        details = fields.get('details')
        details = cast(list[Any], details) if isinstance(details, list) else []
        return Error.new(
            code if isinstance(code, int) else res.code,
            str(fields.get('message') or res.message or ''),
            status=str(status) if (status := fields.get('status')) else None,
            reason=_reason(fields.get('errors'), details),
            details=details,
            tx=tx,
        )

    def parse(self, tx: Pyjo.Transaction.HTTP.object) -> Any:
        """::

            result = call.parse(tx)

        The JSON of a response with a successful status, its body of a type
        that is not JSON or of a request with ``alt=media``, or ``None``
        without a body.
        """
        res = tx.res
        if not res.body:
            return None
        if tx.req.url.query.param('alt') != 'media' and 'json' in (res.headers.content_type or 'json'):
            return res.json()
        return res.body

    def result(self, tx: Pyjo.Transaction.HTTP.object) -> Any:
        """::

            result = call.result(tx)

        The result of the response of the call, of :meth:`parse`, or the
        :mod:`Pyjo.GCP.Error` of :meth:`error` raised for an error status.
        """
        if (code := tx.res.code) is None or code >= 300:
            raise self.error(tx)
        return self.parse(tx)


def url_for(url: Pyjo.URL.object, path: str, query: Mapping[str, Any] | None = None) -> Pyjo.URL.object:
    """::

        url = Pyjo.GCP.Call.url_for(url, '/storage/v1/b', {'project': 'myproject', 'maxResults': 10})

    The URL of the path of a call, after the path of an endpoint, with a
    path that is percent-encoded already, as ``/a%2Fb``, and the parameters
    of a query, whose values of :func:`value_of` are added to those of the
    path, a parameter of each value of a list, and none of ``None``.
    """
    target = Pyjo.URL.new(path)
    url.path = url.path.to_str().rstrip('/') + (target.path.to_str() or '/')
    url.query = target.query
    for name, value in (query or {}).items():
        values = cast(list[Any], value) if isinstance(value, (list, tuple)) else [value]
        if strings := [value_of(v) for v in values if v is not None]:
            url.query.append({name: strings})
    return url


def value_of(value: Any) -> str:
    """::

        string = Pyjo.GCP.Call.value_of(True)

    A value of a parameter as the APIs of Google read it, ``true`` or
    ``false`` of a boolean, and the string of anything else.
    """
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


# The reason of the older format, of errors, or of the detail google.rpc.ErrorInfo of google.rpc.Status
def _reason(errors: Any, details: list[Any]) -> str | None:
    if isinstance(errors, list) and errors and isinstance(first := cast(list[Any], errors)[0], dict):
        if reason := cast(dict[str, Any], first).get('reason'):
            return str(reason)
    for detail in details:
        if isinstance(detail, dict) and str(cast(dict[str, Any], detail).get('@type', '')).endswith('.ErrorInfo'):
            if reason := cast(dict[str, Any], detail).get('reason'):
                return str(reason)
    return None


new = Pyjo_GCP_Call.new
object = Pyjo_GCP_Call
Call = Pyjo_GCP_Call
