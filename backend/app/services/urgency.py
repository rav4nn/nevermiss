from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

UrgencyTier = Literal[
    "critical",
    "urgent",
    "soon",
    "on_radar",
    "passive",
    "recently_expired",
]


def _today_in_timezone(user_tz: str) -> date:
    return datetime.now(ZoneInfo(user_tz)).date()


def compute_urgency(expiry_date: date, user_tz: str) -> tuple[UrgencyTier, int] | None:
    days_remaining = (expiry_date - _today_in_timezone(user_tz)).days

    if days_remaining < -90:
        return None
    if days_remaining < 0:
        return ("recently_expired", days_remaining)
    if days_remaining < 7:
        return ("critical", days_remaining)
    if days_remaining < 30:
        return ("urgent", days_remaining)
    if days_remaining < 90:
        return ("soon", days_remaining)
    if days_remaining < 365:
        return ("on_radar", days_remaining)
    return ("passive", days_remaining)
