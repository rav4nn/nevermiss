from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pytest

from app.models.dismissed_signature import DismissedSignature
from app.services import signatures


@dataclass
class _StoredSignature:
    user_id: uuid.UUID
    signature: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class _FakeSession:
    def __init__(self) -> None:
        self.store: dict[tuple[uuid.UUID, str], _StoredSignature] = {}
        self.flush_count = 0

    def add(self, record: DismissedSignature) -> None:
        self.store[(record.user_id, record.signature)] = _StoredSignature(
            user_id=record.user_id,
            signature=record.signature,
        )

    async def delete(self, record: DismissedSignature) -> None:
        self.store.pop((record.user_id, record.signature), None)

    async def flush(self) -> None:
        self.flush_count += 1


def test_compute_signature_is_consistent_and_case_insensitive() -> None:
    first = signatures.compute_signature("Canva Pro", "subscription", date(2026, 1, 1))
    second = signatures.compute_signature("CANVA PRO", "subscription", date(2026, 1, 1))
    third = signatures.compute_signature("canva pro", "subscription", date(2026, 1, 1))

    assert len(first) == 64
    assert first == second == third


@pytest.mark.asyncio
async def test_add_check_remove_dismissed_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    user_id = uuid.uuid4()
    signature = signatures.compute_signature("Canva Pro", "subscription", date(2026, 1, 1))

    async def fake_get_dismissed_signature(
        _session: _FakeSession,
        user_id_value: uuid.UUID,
        signature_value: str,
    ) -> _StoredSignature | None:
        return _session.store.get((user_id_value, signature_value))

    monkeypatch.setattr(signatures, "_get_dismissed_signature", fake_get_dismissed_signature)

    assert await signatures.is_dismissed(session, user_id, signature) is False

    await signatures.add_dismissed(session, user_id, signature)
    assert await signatures.is_dismissed(session, user_id, signature) is True

    await signatures.remove_dismissed(session, user_id, signature)
    assert await signatures.is_dismissed(session, user_id, signature) is False

    assert session.flush_count == 2
