from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.db import UserTier
from app.core.errors import AppError, ErrorCode
from app.services.tier import require_pro


def test_require_pro_raises_for_free_user() -> None:
    free_user = SimpleNamespace(tier=UserTier.FREE)

    with pytest.raises(AppError) as exc_info:
        require_pro(free_user)

    error = exc_info.value
    assert error.code == ErrorCode.TIER_REQUIRED
    assert error.status_code == 403


def test_require_pro_allows_pro_user() -> None:
    pro_user = SimpleNamespace(tier=UserTier.PRO)

    require_pro(pro_user)
