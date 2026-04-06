from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import scan as scan_api
from app.core.db import ScanKind, ScanStatus, UserTier, get_db
from app.core.errors import AppError, ErrorCode, register_exception_handlers
from app.deps import get_current_user
from app.schemas.scan import ScanStartRequest
from app.services import scan_queue


@dataclass
class _FakeUser:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    tier: UserTier = UserTier.FREE
    refresh_token_enc: str | None = "encrypted-refresh"


@dataclass
class _FakeScanJob:
    user_id: uuid.UUID
    kind: ScanKind
    status: ScanStatus
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    emails_total: int = 0
    emails_processed: int = 0
    items_found: int = 0
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime(2026, 4, 6, 12, 0, tzinfo=UTC))


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[_FakeScanJob] = []
        self.commit_count = 0
        self.refresh_count = 0

    def add(self, job: _FakeScanJob) -> None:
        self.added.append(job)

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, _job: _FakeScanJob) -> None:
        self.refresh_count += 1


@pytest.mark.asyncio
async def test_enqueue_scan_creates_job_when_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    user = _FakeUser(tier=UserTier.PRO)
    payload = ScanStartRequest(kind=ScanKind.MANUAL)

    async def fake_active_scan(_session: _FakeSession, _user: _FakeUser) -> None:
        return None

    monkeypatch.setattr(scan_queue, "_get_active_scan_for_user", fake_active_scan)
    monkeypatch.setattr(scan_queue, "check_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(scan_queue, "ScanJob", _FakeScanJob)

    job = await scan_queue.enqueue_scan(session, user, payload)

    assert job.status == ScanStatus.QUEUED
    assert job.kind == ScanKind.MANUAL
    assert session.commit_count == 1
    assert session.refresh_count == 1
    assert session.added == [job]


@pytest.mark.asyncio
async def test_enqueue_scan_raises_when_active_job_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    user = _FakeUser()
    payload = ScanStartRequest(kind=ScanKind.INITIAL)

    async def fake_active_scan(_session: _FakeSession, _user: _FakeUser) -> _FakeScanJob:
        return _FakeScanJob(user_id=user.id, kind=ScanKind.INITIAL, status=ScanStatus.RUNNING)

    monkeypatch.setattr(scan_queue, "_get_active_scan_for_user", fake_active_scan)
    monkeypatch.setattr(scan_queue, "check_rate_limit", lambda *args, **kwargs: None)

    with pytest.raises(AppError) as exc_info:
        await scan_queue.enqueue_scan(session, user, payload)

    assert exc_info.value.code == ErrorCode.SCAN_IN_PROGRESS
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_enqueue_scan_requires_pro_for_manual(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    user = _FakeUser(tier=UserTier.FREE)
    payload = ScanStartRequest(kind=ScanKind.MANUAL)

    async def fake_active_scan(_session: _FakeSession, _user: _FakeUser) -> None:
        return None

    monkeypatch.setattr(scan_queue, "_get_active_scan_for_user", fake_active_scan)
    monkeypatch.setattr(scan_queue, "check_rate_limit", lambda *args, **kwargs: None)

    with pytest.raises(AppError) as exc_info:
        await scan_queue.enqueue_scan(session, user, payload)

    assert exc_info.value.code == ErrorCode.TIER_REQUIRED
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_latest_scan_raises_not_found_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ScalarResult:
        @staticmethod
        def scalar_one_or_none() -> None:
            return None

    class _QuerySession:
        async def execute(self, _statement: object) -> _ScalarResult:
            return _ScalarResult()

    with pytest.raises(AppError) as exc_info:
        await scan_queue.get_latest_scan(_QuerySession(), _FakeUser())

    assert exc_info.value.code == ErrorCode.NOT_FOUND
    assert exc_info.value.status_code == 404


def test_scan_routes_return_expected_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(scan_api.router)
    user = _FakeUser(tier=UserTier.PRO)
    job = _FakeScanJob(user_id=user.id, kind=ScanKind.INITIAL, status=ScanStatus.QUEUED)

    async def fake_current_user() -> _FakeUser:
        return user

    async def fake_get_db() -> object:
        return object()

    async def fake_enqueue_scan(
        _db: object,
        current_user: _FakeUser,
        payload: ScanStartRequest,
    ) -> _FakeScanJob:
        assert current_user is user
        assert payload.kind == ScanKind.INITIAL
        return job

    async def fake_latest_scan(_db: object, current_user: _FakeUser) -> _FakeScanJob:
        assert current_user is user
        return _FakeScanJob(user_id=user.id, kind=ScanKind.INITIAL, status=ScanStatus.COMPLETE)

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(scan_api, "enqueue_scan", fake_enqueue_scan)
    monkeypatch.setattr(scan_api, "get_latest_scan", fake_latest_scan)

    client = TestClient(app)

    start_response = client.post("/api/scan/start", json={"kind": "initial"})
    assert start_response.status_code == 202
    assert start_response.json() == {"jobId": str(job.id), "status": "queued"}

    status_response = client.get("/api/scan/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "complete"
