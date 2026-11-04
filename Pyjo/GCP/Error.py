"""
Pyjo.GCP.Error - Error of an API of Google Cloud
================================================
::

    from Pyjo.GCP.Call import Call
    from Pyjo.GCP.Client import Client
    from Pyjo.GCP.Error import Error

    try:
        Client(service='storage').call(Call('GET', '/storage/v1/b/mybucket/o/missing'))
    except Error as e:
        print(e.code, e.status, e.reason, e.message)

:mod:`Pyjo.GCP.Error` is the error that an API of Google Cloud responds
with, which a call of :mod:`Pyjo.GCP.Client` raises, or rejects its promise
with, as :mod:`Pyjo.GCP.Call` reads it of the response, the JSON of
``google.rpc.Status`` in ``error``: ::

    {
      "error": {
        "code": 403,
        "message": "Cloud Storage API has not been used in project 123 before or it is disabled.",
        "status": "PERMISSION_DENIED",
        "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "SERVICE_DISABLED"}]
      }
    }

and the older format of Cloud Storage and others, without ``status`` and
with the reason in ``errors``: ::

    {"error": {"code": 404, "message": "No such object: mybucket/missing",
               "errors": [{"message": "No such object: mybucket/missing", "domain": "global", "reason": "notFound"}]}}

See also
--------

:mod:`Pyjo.GCP.Client`, :mod:`Pyjo.GCP.Call`, :mod:`Pyjo.Exception`,
https://google.aip.dev/193.

Classes
-------
"""

import Pyjo.Exception
import Pyjo.Transaction.HTTP

from typing import Any


class Pyjo_GCP_Error(Pyjo.Exception.object):
    """
    :mod:`Pyjo.GCP.Error` inherits all attributes and methods from
    :mod:`Pyjo.Exception` and implements the following new ones.
    """

    def __init__(
        self,
        code: int | None,
        message: str = '',
        *,
        status: str | None = None,
        reason: str | None = None,
        details: list[Any] | None = None,
        tx: Pyjo.Transaction.HTTP.object | None = None,
    ) -> None:
        """::

            e = Pyjo.GCP.Error.new(404, 'No such object: mybucket/missing', status='NOT_FOUND', reason='notFound')

        Construct a new :mod:`Pyjo.GCP.Error` object, whose
        :attr:`~Pyjo.Exception.Pyjo_Exception.message` is the code, the
        status and the message of Google Cloud, as
        ``404 NOT_FOUND: No such object: mybucket/missing``.
        """
        prefix = ' '.join(str(part) for part in (code, status) if part is not None) or 'Error'
        super().__init__(f'{prefix}: {message}' if message else prefix)

        self.code = code
        """::

            code = e.code

        The code of the error, the status of HTTP, as ``404``, or ``None`` of
        a response without one.
        """

        self.status = status
        """::

            status = e.status

        The status of ``google.rpc.Code``, as ``NOT_FOUND``, or ``None`` of an
        API that has none, as Cloud Storage.
        """

        self.reason = reason
        """::

            reason = e.reason

        The reason of the error, of ``reason`` of ``errors``, as ``notFound``,
        or of the detail ``google.rpc.ErrorInfo``, as ``SERVICE_DISABLED``, or
        ``None``.
        """

        self.details: list[Any] = details or []
        """::

            details = e.details

        The details of the error, of ``details``, as ``google.rpc.ErrorInfo``,
        or an empty list.
        """

        self.tx = tx
        """::

            tx = e.tx

        The transaction of the request and its response, or ``None``.
        """


new = Pyjo_GCP_Error.new
object = Pyjo_GCP_Error
Error = Pyjo_GCP_Error
