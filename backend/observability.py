"""Request correlation and log setup.

Every log line carries the id of the request that produced it, so a single user
report can be traced through the whole stack. Structured key=value fields are
used rather than prose so the lines stay greppable and can be parsed by a log
aggregator without a custom regex.
"""

import logging
import uuid
from contextvars import ContextVar

# A ContextVar rather than a global: each request gets its own value, and it is
# correct under async concurrency where many requests interleave on one thread.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_FORMAT = "%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s %(message)s"


class RequestIdFilter(logging.Filter):
    """Injects the current request id into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]
