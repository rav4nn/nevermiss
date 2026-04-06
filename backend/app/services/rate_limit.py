from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic

from app.core.errors import AppError, ErrorCode

_RATE_LIMIT_STATE: dict[str, deque[float]] = {}
_RATE_LIMIT_LOCK = Lock()


def _now() -> float:
    return monotonic()


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    current_time = _now()

    with _RATE_LIMIT_LOCK:
        timestamps = _RATE_LIMIT_STATE.setdefault(key, deque())
        window_start = current_time - window_seconds

        while timestamps and timestamps[0] <= window_start:
            timestamps.popleft()

        if len(timestamps) >= limit:
            raise AppError(
                ErrorCode.RATE_LIMITED,
                "Rate limit exceeded.",
                status_code=429,
            )

        timestamps.append(current_time)

