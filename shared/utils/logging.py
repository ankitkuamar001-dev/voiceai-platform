"""Shared logging configuration with structured JSON output and correlation IDs.

Provides:
  • JSONFormatter      — Structured JSON log format for production
  • setup_logging()    — Configure a service logger
  • RequestIdMiddleware — FastAPI middleware for X-Request-Id propagation
  • get_request_id()   — Get current request's correlation ID
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# ── Context Variable for Request ID ──
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request's correlation ID."""
    return _request_id_var.get()


# ── PII Redaction (lazy import to avoid circular deps) ──

def _redact(text: str) -> str:
    try:
        from shared.utils.security import redact_pii
        return redact_pii(text)
    except ImportError:
        return text


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter with correlation ID and PII redaction."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        message = _redact(message)

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "service": os.getenv("APP_SERVICE", "unknown"),
        }

        # Request correlation ID
        request_id = get_request_id()
        if request_id:
            log_entry["request_id"] = request_id

        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        if hasattr(record, "org_id"):
            log_entry["org_id"] = record.org_id

        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id

        # HTTP context
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["status"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        return json.dumps(log_entry, default=str)


def setup_logging(
    service_name: str,
    level: str | None = None,
) -> logging.Logger:
    """Set up structured logging for a service.

    Args:
        service_name: Name of the service (e.g. "auth-service")
        level: Log level override (default: from LOG_LEVEL env or INFO)

    Returns:
        Configured logger instance.
    """
    os.environ["APP_SERVICE"] = service_name
    log_level = level or os.getenv("LOG_LEVEL", "INFO")
    log_format = os.getenv("LOG_FORMAT", "json")

    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | [%(request_id)s] %(message)s",
                defaults={"request_id": ""},
            )
        )

    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    return logger


# ── FastAPI Middleware for Request ID Propagation ──


class RequestIdMiddleware:
    """ASGI middleware that propagates X-Request-Id through the request lifecycle.

    Usage::

        app = FastAPI()
        app.add_middleware(RequestIdMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract or generate request ID
        headers = dict(scope.get("headers", []))
        request_id = (
            headers.get(b"x-request-id", b"").decode()
            or str(uuid.uuid4())
        )

        # Store in context var for this request
        token = _request_id_var.set(request_id)

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                # Inject X-Request-Id into response headers
                headers = list(message.get("headers", []))
                headers.append([b"x-request-id", request_id.encode()])
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            _request_id_var.reset(token)
