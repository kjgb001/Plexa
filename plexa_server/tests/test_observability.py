from __future__ import annotations

import json
import logging
import sys

from plexa_server.observability import JsonFormatter


def test_json_formatter_does_not_serialize_exception_content() -> None:
    try:
        raise RuntimeError("sensitive upstream response")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="plexa.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Request failed",
        args=(),
        exc_info=exc_info,
    )
    record.request_id = "request-123"

    formatted = JsonFormatter().format(record)
    payload = json.loads(formatted)

    assert payload["exception_type"] == "RuntimeError"
    assert payload["request_id"] == "request-123"
    assert "sensitive upstream response" not in formatted
    assert "exception" not in payload
