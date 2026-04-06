from __future__ import annotations

import pytest

from app.core.errors import AppError, ErrorCode
from app.services import rate_limit


def test_check_rate_limit_allows_up_to_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    key = "scan:user-1"
    rate_limit._RATE_LIMIT_STATE.clear()
    current = {"value": 1000.0}

    monkeypatch.setattr(rate_limit, "_now", lambda: current["value"])

    rate_limit.check_rate_limit(key, limit=2, window_seconds=60)
    rate_limit.check_rate_limit(key, limit=2, window_seconds=60)


def test_check_rate_limit_raises_after_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    key = "scan:user-2"
    rate_limit._RATE_LIMIT_STATE.clear()
    monkeypatch.setattr(rate_limit, "_now", lambda: 1000.0)

    rate_limit.check_rate_limit(key, limit=1, window_seconds=60)

    with pytest.raises(AppError) as exc_info:
        rate_limit.check_rate_limit(key, limit=1, window_seconds=60)

    error = exc_info.value
    assert error.code == ErrorCode.RATE_LIMITED
    assert error.status_code == 429


def test_check_rate_limit_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    key = "scan:user-3"
    rate_limit._RATE_LIMIT_STATE.clear()
    current = {"value": 1000.0}

    monkeypatch.setattr(rate_limit, "_now", lambda: current["value"])

    rate_limit.check_rate_limit(key, limit=1, window_seconds=60)
    current["value"] = 1061.0
    rate_limit.check_rate_limit(key, limit=1, window_seconds=60)
