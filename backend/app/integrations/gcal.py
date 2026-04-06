from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core import crypto
from app.core.errors import AppError, ErrorCode
from app.models.item import ExtractedItem
from app.models.user import User

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GCAL_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _to_iso_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _build_credentials(user: User) -> Credentials:
    if not user.refresh_token_enc:
        raise AppError(
            ErrorCode.GMAIL_REAUTH_REQUIRED,
            "Google account re-authorization is required.",
            status_code=400,
        )

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise AppError(
            ErrorCode.INTERNAL,
            "Google OAuth configuration is missing.",
            status_code=500,
        )

    refresh_token = crypto.decrypt(user.refresh_token_enc)
    access_token = crypto.decrypt(user.access_token_enc) if user.access_token_enc else None
    expiry = user.access_token_expires_at
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)

    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=GCAL_SCOPES,
    )
    credentials.expiry = expiry

    if not credentials.token or credentials.expired:
        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            raise AppError(
                ErrorCode.GMAIL_REAUTH_REQUIRED,
                "Google account re-authorization is required.",
                status_code=400,
            ) from exc

        if credentials.token:
            user.access_token_enc = crypto.encrypt(credentials.token)
        if credentials.expiry is not None:
            user.access_token_expires_at = credentials.expiry

    return credentials


def _build_event_body(item: ExtractedItem) -> dict[str, object]:
    return {
        "summary": item.name,
        "description": (
            f"Category: {item.category.value}\n"
            f"Source: {item.source_sender} on {_to_iso_z(item.source_date)}\n"
            "Detected by NeverMiss"
        ),
        "start": {"date": item.expiry_date.isoformat()},
        "end": {"date": (item.expiry_date + timedelta(days=1)).isoformat()},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10080},
                {"method": "popup", "minutes": 1440},
            ],
        },
    }


def insert_calendar_event(user: User, item: ExtractedItem) -> dict[str, str]:
    credentials = _build_credentials(user)
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    try:
        event = (
            service.events()
            .insert(calendarId="primary", body=_build_event_body(item))
            .execute()
        )
    except HttpError as exc:
        status_code = getattr(getattr(exc, "resp", None), "status", None)
        if status_code in {401, 403}:
            raise AppError(
                ErrorCode.GMAIL_REAUTH_REQUIRED,
                "Google account re-authorization is required.",
                status_code=400,
            ) from exc
        raise AppError(
            ErrorCode.INTERNAL,
            "Failed to export item to Google Calendar.",
            status_code=500,
        ) from exc

    event_id = event.get("id")
    html_link = event.get("htmlLink")
    if not isinstance(event_id, str) or not isinstance(html_link, str):
        raise AppError(
            ErrorCode.INTERNAL,
            "Google Calendar did not return a valid event response.",
            status_code=500,
        )

    return {"gcalEventId": event_id, "htmlLink": html_link}
