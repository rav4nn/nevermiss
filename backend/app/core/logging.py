from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog


def _is_pretty_logging_enabled() -> bool:
    raw_value = os.getenv("LOG_PRETTY")
    if raw_value is not None:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    environment = os.getenv("APP_ENV", "").strip().lower()
    return environment in {"dev", "development", "local"}


def _shared_processors() -> list[structlog.typing.Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def setup_logging() -> None:
    renderer: structlog.typing.Processor
    if _is_pretty_logging_enabled():
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    processors = [
        *_shared_processors(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_shared_processors(),
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_log_context(
    *,
    user_id: str | None = None,
    job_id: str | None = None,
    **extra: Any,
) -> None:
    values: dict[str, Any] = dict(extra)
    if user_id is not None:
        values["user_id"] = user_id
    if job_id is not None:
        values["job_id"] = job_id
    if values:
        structlog.contextvars.bind_contextvars(**values)


def unbind_log_context(*keys: str) -> None:
    if keys:
        structlog.contextvars.unbind_contextvars(*keys)


def clear_log_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str | None = None, **bindings: Any) -> structlog.stdlib.BoundLogger:
    logger = structlog.get_logger(name)
    if bindings:
        logger = logger.bind(**bindings)
    return logger
