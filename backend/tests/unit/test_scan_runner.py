from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pytest

from app.core.db import ConfidenceLevel, DateType, ItemCategory, ScanKind, ScanStatus, UserTier
from app.integrations.gmail import GmailReauthRequired
from app.workers import scan_runner


@dataclass
class _FakeUser:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    tier: UserTier = UserTier.FREE
    last_scan_at: datetime | None = None
    deleted_at: datetime | None = None
    refresh_token_enc: str | None = "enc-refresh"
    access_token_enc: str | None = "enc-access"
    access_token_expires_at: datetime | None = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


@dataclass
class _FakeJob:
    user_id: uuid.UUID
    kind: ScanKind
    status: ScanStatus = ScanStatus.RUNNING
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class _Extraction:
    name: str = "Canva Pro"
    category: ItemCategory = ItemCategory.SUBSCRIPTION
    date: date = date(2026, 1, 1)
    date_type: DateType = DateType.EXPIRY
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    notes: str = ""


class _ExecuteResult:
    def __init__(self, *, rowcount: int = 1, scalar=None) -> None:
        self.rowcount = rowcount
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class _FakeBatchSession:
    def __init__(self) -> None:
        self.executed = 0

    async def execute(self, statement) -> _ExecuteResult:
        self.executed += 1
        params = statement.compile().params
        item_name = params.get("name")
        return _ExecuteResult(rowcount=0 if item_name == "Duplicate" else 1)


class _FakeRunSession:
    def __init__(self, user: _FakeUser) -> None:
        self.user = user
        self.failures: list[str] = []

    async def execute(self, statement):
        statement_text = str(statement)
        if "FROM users" in statement_text:
            return _ExecuteResult(scalar=self.user)
        return _ExecuteResult()

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_since_date_covers_all_supported_kinds(monkeypatch: pytest.MonkeyPatch) -> None:
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 7, 12, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(scan_runner, "datetime", FrozenDateTime)

    free_user = _FakeUser(tier=UserTier.FREE)
    pro_user = _FakeUser(tier=UserTier.PRO)
    weekly_user = _FakeUser(
        tier=UserTier.PRO,
        last_scan_at=datetime(2026, 4, 1, 9, 30, tzinfo=UTC),
    )

    assert scan_runner._since_date(
        _FakeJob(free_user.id, ScanKind.INITIAL), free_user
    ) == date(2026, 1, 7)
    assert scan_runner._since_date(
        _FakeJob(pro_user.id, ScanKind.INITIAL), pro_user
    ) == date(2025, 3, 3)
    assert scan_runner._since_date(
        _FakeJob(weekly_user.id, ScanKind.WEEKLY), weekly_user
    ) == date(2026, 4, 1)
    assert scan_runner._since_date(
        _FakeJob(pro_user.id, ScanKind.MANUAL), pro_user
    ) == date(2026, 1, 7)


@pytest.mark.asyncio
async def test_process_batch_counts_only_new_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeBatchSession()
    user = _FakeUser()
    sent_at = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)

    async def fake_fetch_body(_service, message_id: str):
        return ("body", f"{message_id}@example.com", sent_at)

    async def fake_is_dismissed(_session, _user_id, _signature):
        return False

    def fake_extract_items(_body, _sender, _sent_at, _user):
        return [
            _Extraction(name="Unique"),
            _Extraction(name="Duplicate"),
        ]

    monkeypatch.setattr(scan_runner, "_fetch_body", fake_fetch_body)
    monkeypatch.setattr(scan_runner.signatures, "is_dismissed", fake_is_dismissed)
    monkeypatch.setattr(scan_runner.gemini, "extract_items", fake_extract_items)

    inserted = await scan_runner._process_batch(session, user, object(), ["msg-1"])

    assert inserted == 1
    assert session.executed == 2


@pytest.mark.asyncio
async def test_run_job_clears_refresh_token_when_gmail_reauth_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _FakeUser()
    job = _FakeJob(user_id=user.id, kind=ScanKind.INITIAL)
    session = _FakeRunSession(user)
    observed: dict[str, str] = {}

    def fake_build_gmail_service(*args, **kwargs):
        raise GmailReauthRequired()

    async def fake_handle_reauth(_db, current_user: _FakeUser, current_job: _FakeJob) -> None:
        observed["user_id"] = str(current_user.id)
        observed["job_id"] = str(current_job.id)

    monkeypatch.setattr(scan_runner.gmail, "build_gmail_service", fake_build_gmail_service)
    monkeypatch.setattr(scan_runner, "_handle_reauth", fake_handle_reauth)

    await scan_runner._run_job(session, job)

    assert observed == {"user_id": str(user.id), "job_id": str(job.id)}


@pytest.mark.asyncio
async def test_process_batch_deletes_body_local_before_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeBatchSession()
    user = _FakeUser()
    captured_locals: dict[str, object] = {}

    async def fake_fetch_body(_service, _message_id: str):
        return ("email-body", "sender@example.com", datetime(2026, 4, 6, 12, 0, tzinfo=UTC))

    async def fake_is_dismissed(_session, _user_id, _signature):
        return False

    def fake_extract_items(_body, _sender, _sent_at, _user):
        return []

    def profiler(frame, event, arg):
        if event == "return" and frame.f_code is scan_runner._process_batch.__code__:
            captured_locals.update(frame.f_locals)
        return profiler

    monkeypatch.setattr(scan_runner, "_fetch_body", fake_fetch_body)
    monkeypatch.setattr(scan_runner.signatures, "is_dismissed", fake_is_dismissed)
    monkeypatch.setattr(scan_runner.gemini, "extract_items", fake_extract_items)

    previous_profiler = sys.getprofile()
    sys.setprofile(profiler)
    try:
        await scan_runner._process_batch(session, user, object(), ["msg-1"])
    finally:
        sys.setprofile(previous_profiler)

    assert "body" not in captured_locals
