from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from techbrief.context import get_request_id, get_run_id, get_service


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.run_id = get_run_id() or "-"
        record.service = get_service() or os.getenv("TECHBRIEF_SERVICE", "web")
        record.env = os.getenv("APP_ENV", "local")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "env": getattr(record, "env", os.getenv("APP_ENV", "local")),
            "service": getattr(record, "service", os.getenv("TECHBRIEF_SERVICE", "web")),
            "request_id": getattr(record, "request_id", "-"),
            "run_id": getattr(record, "run_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"{timestamp} {record.levelname} {record.name} "
            f"request_id={getattr(record, 'request_id', '-')} "
            f"run_id={getattr(record, 'run_id', '-')} "
            f"{record.getMessage()}"
        )
