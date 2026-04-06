from __future__ import annotations

import base64
import os
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from app.core import crypto
from app.core.logging import get_logger

logger = get_logger("integrations.gmail")

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GMAIL_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
MAX_BODY_LENGTH = 8000


class GmailReauthRequired(RuntimeError):
    """Raised when Gmail credentials are no longer valid and the user must reconnect."""


class _HTMLToTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(part.strip() for part in self._parts if part.strip())


def _google_client_id() -> str:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID is not configured.")
    return client_id


def _google_client_secret() -> str:
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_secret:
        raise RuntimeError("GOOGLE_CLIENT_SECRET is not configured.")
    return client_secret


def _is_invalid_grant_error(exc: Exception) -> bool:
    return "invalid_grant" in str(exc).lower()


def _truncate_body(body: str) -> str:
    return body[:MAX_BODY_LENGTH]


def _decode_body(data: str | None) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(f"{data}{padding}".encode())
    return decoded.decode("utf-8", errors="ignore")


def _html_to_text(html: str) -> str:
    try:
        import html2text  # type: ignore[import-not-found]
    except Exception:
        parser = _HTMLToTextParser()
        parser.feed(html)
        return parser.get_text()

    parser = html2text.HTML2Text()
    parser.ignore_links = True
    parser.ignore_images = True
    return parser.handle(html).strip()


def _extract_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [payload]
    for child in payload.get("parts", []) or []:
        parts.extend(_extract_parts(child))
    return parts


def _header_value(headers: list[dict[str, str]], name: str) -> str | None:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value")
    return None


@retry(
    retry=retry_if_not_exception_type(GmailReauthRequired),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    stop=stop_after_attempt(3),
    reraise=True,
)
def build_gmail_service(
    refresh_token_enc: str,
    access_token_enc: str | None,
    expires_at: datetime | None,
) -> Resource:
    refresh_token = crypto.decrypt(refresh_token_enc)
    access_token = crypto.decrypt(access_token_enc) if access_token_enc else None

    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=_google_client_id(),
        client_secret=_google_client_secret(),
        scopes=GMAIL_SCOPES,
    )

    if expires_at is not None:
        credentials.expiry = expires_at if expires_at.tzinfo is not None else expires_at.replace(
            tzinfo=UTC
        )

    if not credentials.token or credentials.expired:
        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            if _is_invalid_grant_error(exc):
                raise GmailReauthRequired("Google refresh token is invalid.") from exc
            raise

    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    refreshed_state = {
        "access_token_enc": crypto.encrypt(credentials.token) if credentials.token else None,
        "access_token_expires_at": credentials.expiry,
    }
    service._nevermiss_token_state = refreshed_state  # type: ignore[attr-defined]
    return service


@retry(
    retry=retry_if_not_exception_type(GmailReauthRequired),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    stop=stop_after_attempt(3),
    reraise=True,
)
def list_message_ids(service: Resource, since_date: date) -> list[str]:
    message_ids: list[str] = []
    page_token: str | None = None
    query = f"after:{since_date.strftime('%Y/%m/%d')}"

    while True:
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token)
            .execute()
        )
        message_ids.extend(
            message["id"] for message in response.get("messages", []) if "id" in message
        )
        page_token = response.get("nextPageToken")
        if not page_token:
            return message_ids


@retry(
    retry=retry_if_not_exception_type(GmailReauthRequired),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    stop=stop_after_attempt(3),
    reraise=True,
)
def get_message_body(service: Resource, message_id: str) -> tuple[str, str, datetime]:
    response = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    payload = response.get("payload", {})
    headers = payload.get("headers", []) or []
    sender = _header_value(headers, "From") or ""

    internal_date_raw = response.get("internalDate")
    if isinstance(internal_date_raw, str) and internal_date_raw.isdigit():
        sent_at = datetime.fromtimestamp(int(internal_date_raw) / 1000, tz=UTC)
    else:
        parsed_header = _header_value(headers, "Date")
        if not parsed_header:
            sent_at = datetime.now(UTC)
        else:
            parsed_dt = parsedate_to_datetime(parsed_header)
            sent_at = parsed_dt if parsed_dt.tzinfo is not None else parsed_dt.replace(tzinfo=UTC)

    plain_text = ""
    html_text = ""
    for part in _extract_parts(payload):
        mime_type = part.get("mimeType")
        body = part.get("body", {})
        data = _decode_body(body.get("data"))
        if mime_type == "text/plain" and data:
            plain_text = data
            break
        if mime_type == "text/html" and data and not html_text:
            html_text = data

    body_text = plain_text or _html_to_text(html_text)
    return (_truncate_body(body_text), sender, sent_at)


@retry(
    retry=retry_if_not_exception_type(GmailReauthRequired),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    stop=stop_after_attempt(3),
    reraise=True,
)
def revoke_token(refresh_token: str) -> None:
    from urllib import parse, request

    revoke_url = "https://oauth2.googleapis.com/revoke?token=" + parse.quote(refresh_token, safe="")
    req = request.Request(revoke_url, data=b"", method="POST")
    with request.urlopen(req, timeout=10):
        logger.info("gmail_token_revoked")
