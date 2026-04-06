from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.core.db import ConfidenceLevel, DateType, ItemCategory, UserTier
from app.integrations import gemini


@dataclass
class _FakeUser:
    api_key_enc: str | None = None
    tier: UserTier = UserTier.FREE


def test_extract_items_returns_empty_list_on_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gemini, "_select_api_key", lambda user: "shared-key")
    monkeypatch.setattr(gemini, "_build_prompt", lambda *args: "prompt")
    monkeypatch.setattr(gemini, "_generate_content", lambda *args: "not-json")

    result = gemini.extract_items(
        "body",
        "sender@example.com",
        datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        _FakeUser(),
    )

    assert result == []


def test_extract_items_filters_dates_older_than_ninety_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gemini, "_select_api_key", lambda user: "shared-key")
    monkeypatch.setattr(gemini, "_build_prompt", lambda *args: "prompt")
    monkeypatch.setattr(
        gemini,
        "_generate_content",
        lambda *args: (
            '[{"name":"Old policy","category":"insurance","date":"2025-01-01",'
            '"date_type":"expiry","confidence":"high","notes":""}]'
        ),
    )
    monkeypatch.setattr(
        gemini,
        "datetime",
        type(
            "_FakeDateTime",
            (),
            {
                "now": staticmethod(lambda tz=None: datetime(2026, 4, 6, 12, 0, tzinfo=UTC)),
            },
        ),
    )

    result = gemini.extract_items(
        "Policy expired on 2025-01-01",
        "sender@example.com",
        datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        _FakeUser(),
    )

    assert result == []


def test_extract_items_uses_byok_when_user_key_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    monkeypatch.setattr(gemini.crypto, "decrypt", lambda value: "byok-key")
    monkeypatch.setattr(gemini, "_build_prompt", lambda *args: "prompt")

    def fake_generate(api_key: str, prompt: str) -> str:
        captured["api_key"] = api_key
        captured["prompt"] = prompt
        return (
            '[{"name":"Canva Pro","category":"subscription","date":"2026-04-20",'
            '"date_type":"renewal","confidence":"high","notes":""}]'
        )

    monkeypatch.setattr(gemini, "_generate_content", fake_generate)
    monkeypatch.setattr(
        gemini,
        "datetime",
        type(
            "_FakeDateTime",
            (),
            {
                "now": staticmethod(lambda tz=None: datetime(2026, 4, 6, 12, 0, tzinfo=UTC)),
            },
        ),
    )

    result = gemini.extract_items(
        "Your Canva Pro renews on 2026-04-20",
        "sender@example.com",
        datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        _FakeUser(api_key_enc="enc-byok"),
    )

    assert captured["api_key"] == "byok-key"
    assert len(result) == 1
    assert result[0].category == ItemCategory.SUBSCRIPTION
    assert result[0].date_type == DateType.RENEWAL
    assert result[0].confidence == ConfidenceLevel.HIGH


def test_extract_items_filters_low_confidence_without_explicit_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gemini, "_select_api_key", lambda user: "shared-key")
    monkeypatch.setattr(gemini, "_build_prompt", lambda *args: "prompt")
    monkeypatch.setattr(
        gemini,
        "_generate_content",
        lambda *args: (
            '[{"name":"Membership","category":"membership","date":"2026-04-20",'
            '"date_type":"renewal","confidence":"low","notes":""}]'
        ),
    )
    monkeypatch.setattr(
        gemini,
        "datetime",
        type(
            "_FakeDateTime",
            (),
            {
                "now": staticmethod(lambda tz=None: datetime(2026, 4, 6, 12, 0, tzinfo=UTC)),
            },
        ),
    )

    result = gemini.extract_items(
        "Your membership renews soon.",
        "sender@example.com",
        datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        _FakeUser(),
    )

    assert result == []
