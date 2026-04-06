from __future__ import annotations

from datetime import date

from app.services import urgency


def test_compute_urgency_returns_critical_for_three_days() -> None:
    original_today_in_timezone = urgency._today_in_timezone
    urgency._today_in_timezone = lambda _user_tz: date(2026, 4, 6)  # type: ignore[assignment]
    try:
        assert urgency.compute_urgency(date(2026, 4, 9), "UTC") == ("critical", 3)
    finally:
        urgency._today_in_timezone = original_today_in_timezone


def test_compute_urgency_excludes_items_older_than_ninety_days() -> None:
    original_today_in_timezone = urgency._today_in_timezone
    urgency._today_in_timezone = lambda _user_tz: date(2026, 4, 6)  # type: ignore[assignment]
    try:
        assert urgency.compute_urgency(date(2025, 12, 27), "UTC") is None
    finally:
        urgency._today_in_timezone = original_today_in_timezone


def test_compute_urgency_returns_recently_expired_with_negative_days() -> None:
    original_today_in_timezone = urgency._today_in_timezone
    urgency._today_in_timezone = lambda _user_tz: date(2026, 4, 6)  # type: ignore[assignment]
    try:
        assert urgency.compute_urgency(date(2026, 4, 1), "UTC") == ("recently_expired", -5)
    finally:
        urgency._today_in_timezone = original_today_in_timezone


def test_compute_urgency_uses_user_timezone_for_today() -> None:
    original_today_in_timezone = urgency._today_in_timezone

    def fake_today_in_timezone(user_tz: str) -> date:
        if user_tz == "UTC":
            return date(2026, 4, 6)
        if user_tz == "Asia/Tokyo":
            return date(2026, 4, 7)
        raise AssertionError(f"Unexpected timezone: {user_tz}")

    urgency._today_in_timezone = fake_today_in_timezone  # type: ignore[assignment]
    try:
        assert urgency.compute_urgency(date(2026, 4, 12), "UTC") == ("critical", 6)
        assert urgency.compute_urgency(date(2026, 4, 12), "Asia/Tokyo") == ("critical", 5)
    finally:
        urgency._today_in_timezone = original_today_in_timezone
