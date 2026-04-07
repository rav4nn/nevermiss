from __future__ import annotations

from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from pydantic import ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.db import UserTier, get_db
from app.core.errors import AppError, ErrorCode
from app.deps import CurrentUser
from app.schemas.common import SchemaBase

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsResponse(SchemaBase):
    tier: UserTier
    has_api_key: bool
    timezone: str
    digest_day_of_week: int


class SettingsUpdateRequest(SchemaBase):
    model_config = ConfigDict(
        alias_generator=SchemaBase.model_config["alias_generator"],
        populate_by_name=True,
    )

    api_key: str | None | object = None
    timezone: str | None = None
    digest_day_of_week: int | None = None


def _serialize_settings(current_user: CurrentUser) -> SettingsResponse:
    return SettingsResponse(
        tier=current_user.tier,
        has_api_key=current_user.api_key_enc is not None,
        timezone=current_user.timezone,
        digest_day_of_week=current_user.digest_day_of_week,
    )


_TZ_ALIASES = {
    "Asia/Calcutta": "Asia/Kolkata",
    "Asia/Ulaanbaatar": "Asia/Ulan_Bator",
    "America/Indiana/Indianapolis": "America/Indianapolis",
}


def _validate_timezone(timezone: str) -> str:
    timezone = _TZ_ALIASES.get(timezone, timezone)
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        # tzdata package may not be installed — fall back to UTC silently
        return "UTC"
    return timezone


def _validate_digest_day_of_week(day: int) -> int:
    if day < 0 or day > 6:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "digestDayOfWeek must be between 0 and 6.",
            status_code=422,
        )
    return day


def _validate_gemini_api_key(api_key: str) -> None:
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        client.models.generate_content(
            model="gemini-2.0-flash",
            contents="test",
            config=types.GenerateContentConfig(max_output_tokens=1),
        )
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Invalid Gemini API key.",
            status_code=422,
        ) from exc


@router.get("", response_model=SettingsResponse)
async def get_settings(current_user: CurrentUser) -> SettingsResponse:
    return _serialize_settings(current_user)


@router.patch("", response_model=SettingsResponse)
async def patch_settings(
    payload: SettingsUpdateRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SettingsResponse:
    update_data = payload.model_dump(exclude_unset=True)

    if "api_key" in update_data:
        api_key = update_data["api_key"]
        if api_key is None:
            current_user.api_key_enc = None
        else:
            if not isinstance(api_key, str):
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    "apiKey must be a string or null.",
                    status_code=422,
                )
            _validate_gemini_api_key(api_key)
            current_user.api_key_enc = crypto.encrypt(api_key)

    if "timezone" in update_data and update_data["timezone"] is not None:
        current_user.timezone = _validate_timezone(update_data["timezone"])

    if "digest_day_of_week" in update_data and update_data["digest_day_of_week"] is not None:
        current_user.digest_day_of_week = _validate_digest_day_of_week(
            update_data["digest_day_of_week"]
        )

    await db.commit()
    await db.refresh(current_user)
    return _serialize_settings(current_user)
