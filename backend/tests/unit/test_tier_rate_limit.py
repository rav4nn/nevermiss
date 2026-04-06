from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.db import UserTier
from app.core.errors import AppError, ErrorCode
from app.services import rate_limit, tier


def test_require_pro_raises_for_free_user() -> None:
    user = SimpleNamespace(tier=UserTier.FREE)

    with pytest.raises(AppError) as exc_info:
        tier.require_pro(user)

    assert exc_info.value.code == ErrorCode.TIER_REQUIRED
    assert exc_info.value.status_code == 403


def test_require_pro_allows_pro_user() -> None:
    user = SimpleNamespace(tier=UserTier.PRO)

    tier.require_pro(user)


def test_check_rate_limit_allows_exact_limit_then_raises() -> None:
    original_now = rate_limit._now
    rate_limit._RATE_LIMIT_STATE.clear()
    values = iter([100.0, 101.0, 102.0, 103.0])
    rate_limit._now = lambda: next(values)  # type: ignore[assignment]

    try:
        rate_limit.check_rate_limit("scan:user-1", limit=3, window_seconds=3600)
        rate_limit.check_rate_limit("scan:user-1", limit=3, window_seconds=3600)
        rate_limit.check_rate_limit("scan:user-1", limit=3, window_seconds=3600)

        with pytest.raises(AppError) as exc_info:
            rate_limit.check_rate_limit("scan:user-1", limit=3, window_seconds=3600)

        assert exc_info.value.code == ErrorCode.RATE_LIMITED
        assert exc_info.value.status_code == 429
    finally:
        rate_limit._now = original_now
        rate_limit._RATE_LIMIT_STATE.clear()


def test_check_rate_limit_resets_after_window() -> None:
    original_now = rate_limit._now
    rate_limit._RATE_LIMIT_STATE.clear()
    values = iter([10.0, 11.0, 71.0])
    rate_limit._now = lambda: next(values)  # type: ignore[assignment]

    try:
        rate_limit.check_rate_limit("export:user-1", limit=2, window_seconds=60)
        rate_limit.check_rate_limit("export:user-1", limit=2, window_seconds=60)
        rate_limit.check_rate_limit("export:user-1", limit=2, window_seconds=60)
    finally:
        rate_limit._now = original_now
        rate_limit._RATE_LIMIT_STATE.clear()
