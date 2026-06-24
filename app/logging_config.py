from __future__ import annotations

import logging
import re
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"nvapi-[A-Za-z0-9_\-]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]+"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]+"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password|pass)=([^&\s]+)"),
]


def redact(text: Any) -> str:
    value = str(text)
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            value = pattern.sub(lambda m: f"{m.group(1)}=***", value)
        else:
            value = pattern.sub("***", value)
    return value


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        return redact(rendered)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
