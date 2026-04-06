from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from app.core.db import ScanKind, ScanStatus, UserTier
from app.models.audit_log import AuditLog
from app.workers import digest_cron, weekly_cron


@dataclass
class _FakeUser:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    email: str = "user@example.com"
    tier: UserTier = UserTier.PRO
    timezone: str = "UTC"
    deleted_at: datetime | None = None


@dataclass
class _FakeScanJob:
    user_id: uuid.UUID
    kind: ScanKind
    status: ScanStatus


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class _WeeklySession:
    def __init__(self, users, active_by_user):
        self.users = users
        self.active_by_user = active_by_user
        self.added = []
        self.commit_count = 0

    async def execute(self, statement):
        statement_text = str(statement)
        if "FROM users" in statement_text:
            return _ScalarResult(self.users)
        user_id = list(statement.compile().params.values())[0]
        active = self.active_by_user.get(user_id)
        return _ScalarResult([active] if active is not None else [])

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commit_count += 1


class _DigestSession:
    def __init__(self, users, recent_digest_user_ids=None):
        self.users = users
        self.recent_digest_user_ids = set(recent_digest_user_ids or [])
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, statement):
        statement_text = str(statement)
        if "FROM users" in statement_text:
            return _ScalarResult(self.users)
        user_id = statement.compile().params["user_id_1"]
        if user_id in self.recent_digest_user_ids:
            return _ScalarResult([AuditLog(user_id=user_id, event="digest_sent", payload={})])
        return _ScalarResult([])

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


@pytest.mark.asyncio
async def test_enqueue_all_pro_users_skips_active_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    user_with_active = _FakeUser()
    user_without_active = _FakeUser()
    session = _WeeklySession(
        [user_with_active, user_without_active],
        {
            user_with_active.id: _FakeScanJob(
                user_id=user_with_active.id,
                kind=ScanKind.WEEKLY,
                status=ScanStatus.QUEUED,
            )
        },
    )

    async def fake_get_db():
        yield session

    monkeypatch.setattr(weekly_cron, "get_db", fake_get_db)

    await weekly_cron.enqueue_all_pro_users()

    assert len(session.added) == 1
    assert session.added[0].user_id == user_without_active.id
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_send_due_digests_only_processes_users_in_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    utc_user = _FakeUser(timezone="UTC")
    tokyo_user = _FakeUser(timezone="Asia/Tokyo")
    session = _DigestSession([utc_user, tokyo_user])
    sent = []

    async def fake_get_db():
        yield session

    async def fake_get_items(_session, user, **kwargs):
        items = [type("Item", (), {"name": "Item", "expiry_date": "2026-04-07"})()]
        return {"items": items if user is utc_user else [], "total": 1 if user is utc_user else 0}

    monkeypatch.setattr(digest_cron, "get_db", fake_get_db)
    monkeypatch.setattr(digest_cron, "_now_utc", lambda: datetime(2026, 4, 6, 8, 15, tzinfo=UTC))
    monkeypatch.setattr(digest_cron, "get_items", fake_get_items)
    monkeypatch.setattr(
        digest_cron,
        "send_email",
        lambda to, subject, html, text: sent.append((to, subject, html, text)),
    )

    await digest_cron.send_due_digests()

    assert len(sent) == 1
    assert sent[0][0] == utc_user.email
    assert "NeverMiss" in sent[0][1]
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_send_due_digests_skips_users_with_recent_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _FakeUser()
    session = _DigestSession([user], recent_digest_user_ids={user.id})

    async def fake_get_db():
        yield session

    monkeypatch.setattr(digest_cron, "get_db", fake_get_db)
    monkeypatch.setattr(digest_cron, "_now_utc", lambda: datetime(2026, 4, 6, 8, 15, tzinfo=UTC))

    def fail_send_email(*args, **kwargs):
        raise RuntimeError("should not send")

    monkeypatch.setattr(digest_cron, "send_email", fail_send_email)

    await digest_cron.send_due_digests()

    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_send_due_digests_logs_and_continues_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_user = _FakeUser(email="first@example.com")
    second_user = _FakeUser(email="second@example.com")
    session = _DigestSession([first_user, second_user])
    sent = []

    async def fake_get_db():
        yield session

    async def fake_get_items(*args, **kwargs):
        return {"items": [], "total": 0}

    def fake_send_email(to, subject, html, text):
        if to == "first@example.com":
            raise RuntimeError("boom")
        sent.append(to)

    monkeypatch.setattr(digest_cron, "get_db", fake_get_db)
    monkeypatch.setattr(digest_cron, "_now_utc", lambda: datetime(2026, 4, 6, 8, 15, tzinfo=UTC))
    monkeypatch.setattr(digest_cron, "get_items", fake_get_items)
    monkeypatch.setattr(digest_cron, "send_email", fake_send_email)

    await digest_cron.send_due_digests()

    assert sent == ["second@example.com"]
    assert session.rollback_count == 1
