from __future__ import annotations

from app.core.db import UserTier
from app.core.errors import AppError, ErrorCode
from app.models.user import User


def require_pro(user: User) -> None:
    if user.tier != UserTier.PRO:
        raise AppError(
            ErrorCode.TIER_REQUIRED,
            "This feature requires a Pro subscription.",
            status_code=403,
        )
