from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import jwt
import pytest
import pytest_asyncio
from alembic.config import Config
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from app.config import get_settings
from app.core import crypto
from app.core.db import (
    ConfidenceLevel,
    DateType,
    ItemCategory,
    ScanKind,
    ScanStatus,
    UserTier,
    get_db,
)
from app.main_api import create_app
from app.models.item import ExtractedItem
from app.models.scan_job import ScanJob
from app.models.user import User
from app.services import rate_limit

TEST_NEXTAUTH_SECRET = "test-nextauth-secret"
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")


@pytest.fixture(autouse=True)
def _reset_runtime_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("NEXTAUTH_SECRET", TEST_NEXTAUTH_SECRET)
    monkeypatch.setenv("ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    get_settings.cache_clear()
    crypto._get_fernet.cache_clear()
    rate_limit._RATE_LIMIT_STATE.clear()
    yield
    get_settings.cache_clear()
    crypto._get_fernet.cache_clear()
    rate_limit._RATE_LIMIT_STATE.clear()


@pytest.fixture
def make_jwt():
    def _make_jwt(user_id: uuid.UUID, *, expires_in_seconds: int = 3600) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        }
        return jwt.encode(payload, TEST_NEXTAUTH_SECRET, algorithm="HS256")

    return _make_jwt


@pytest.fixture
def auth_headers(make_jwt):
    def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_jwt(user_id)}"}

    return _auth_headers


@pytest.fixture(scope="session")
def integration_database_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/nevermiss",
        ),
    )


@pytest_asyncio.fixture(scope="session")
async def integration_engine(integration_database_url: str):
    engine = create_async_engine(integration_database_url, future=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Integration database unavailable: {exc}")

    backend_dir = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(backend_dir / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", integration_database_url)
    command.upgrade(alembic_config, "head")

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def integration_sessionmaker(integration_engine):
    sessionmaker = async_sessionmaker(
        bind=integration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with sessionmaker() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE extracted_items, scan_jobs, dismissed_signatures, audit_log, users "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()

    return sessionmaker


@pytest_asyncio.fixture
async def app(integration_sessionmaker) -> AsyncIterator:
    application = create_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with integration_sessionmaker() as session:
            yield session

    application.dependency_overrides[get_db] = override_get_db
    try:
        yield application
    finally:
        application.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client


@pytest_asyncio.fixture
async def user_factory(integration_sessionmaker):
    async def _create_user(
        *,
        email: str | None = None,
        google_sub: str | None = None,
        tier: UserTier = UserTier.FREE,
        refresh_token_enc: str | None = None,
        access_token_enc: str | None = None,
        dodo_customer_id: str | None = None,
        dodo_subscription_id: str | None = None,
        timezone: str = "UTC",
        deleted_at: datetime | None = None,
    ) -> User:
        async with integration_sessionmaker() as session:
            unique = uuid.uuid4().hex
            user = User(
                email=email or f"user-{unique}@example.com",
                gmail_address=f"gmail-{unique}@example.com",
                google_sub=google_sub or f"google-sub-{unique}",
                refresh_token_enc=(
                    refresh_token_enc
                    if refresh_token_enc is not None
                    else crypto.encrypt("refresh-token")
                ),
                access_token_enc=(
                    access_token_enc
                    if access_token_enc is not None
                    else crypto.encrypt("access-token")
                ),
                access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
                timezone=timezone,
                tier=tier,
                dodo_customer_id=dodo_customer_id,
                dodo_subscription_id=dodo_subscription_id,
                deleted_at=deleted_at,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    return _create_user


@pytest_asyncio.fixture
async def item_factory(integration_sessionmaker):
    async def _create_item(
        user: User,
        *,
        name: str = "Canva Pro",
        category: ItemCategory = ItemCategory.SUBSCRIPTION,
        expiry_date: date | None = None,
        dismissed: bool = False,
        exported_to_gcal: bool = False,
    ) -> ExtractedItem:
        async with integration_sessionmaker() as session:
            effective_expiry = expiry_date or (date.today() + timedelta(days=10))
            item = ExtractedItem(
                user_id=user.id,
                name=name,
                category=category,
                expiry_date=effective_expiry,
                date_type=DateType.EXPIRY,
                confidence=ConfidenceLevel.HIGH,
                notes=None,
                source_sender="sender@example.com",
                source_date=datetime.now(UTC),
                source_message_id=f"msg-{uuid.uuid4()}",
                dismissed=dismissed,
                exported_to_gcal=exported_to_gcal,
            )
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    return _create_item


@pytest_asyncio.fixture
async def scan_job_factory(integration_sessionmaker):
    async def _create_job(
        user: User,
        *,
        kind: ScanKind = ScanKind.INITIAL,
        status: ScanStatus = ScanStatus.QUEUED,
    ) -> ScanJob:
        async with integration_sessionmaker() as session:
            job = ScanJob(
                user_id=user.id,
                kind=kind,
                status=status,
                emails_total=0,
                emails_processed=0,
                items_found=0,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    return _create_job
