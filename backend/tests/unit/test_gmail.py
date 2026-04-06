from __future__ import annotations

import base64
from datetime import UTC, date, datetime

import pytest
from google.auth.exceptions import RefreshError

from app.integrations import gmail


def _b64(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


class _FakeMessagesAPI:
    def __init__(self, pages: list[dict] | None = None, message: dict | None = None) -> None:
        self.pages = pages or []
        self.message = message or {}
        self.page_index = 0

    def list(self, *, userId: str, q: str, pageToken: str | None = None) -> _FakeMessagesAPI:
        self._list_args = {"userId": userId, "q": q, "pageToken": pageToken}
        return self

    def get(self, *, userId: str, id: str, format: str) -> _FakeMessagesAPI:
        self._get_args = {"userId": userId, "id": id, "format": format}
        return self

    def execute(self) -> dict:
        if self.pages:
            response = self.pages[self.page_index]
            self.page_index += 1
            return response
        return self.message


class _FakeUsersAPI:
    def __init__(self, messages_api: _FakeMessagesAPI) -> None:
        self._messages_api = messages_api

    def messages(self) -> _FakeMessagesAPI:
        return self._messages_api


class _FakeService:
    def __init__(self, messages_api: _FakeMessagesAPI) -> None:
        self._users_api = _FakeUsersAPI(messages_api)

    def users(self) -> _FakeUsersAPI:
        return self._users_api


def test_list_message_ids_paginates_all_pages() -> None:
    service = _FakeService(
        _FakeMessagesAPI(
            pages=[
                {"messages": [{"id": "m1"}, {"id": "m2"}], "nextPageToken": "next"},
                {"messages": [{"id": "m3"}]},
            ]
        )
    )

    result = gmail.list_message_ids(service, date(2026, 4, 6))

    assert result == ["m1", "m2", "m3"]


def test_get_message_body_prefers_plaintext_and_truncates() -> None:
    long_body = "x" * 9000
    service = _FakeService(
        _FakeMessagesAPI(
            message={
                "internalDate": "1712404800000",
                "payload": {
                    "headers": [{"name": "From", "value": "sender@example.com"}],
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": _b64(long_body)}},
                        {"mimeType": "text/html", "body": {"data": _b64("<p>html</p>")}},
                    ],
                },
            }
        )
    )

    body, sender, sent_at = gmail.get_message_body(service, "m1")

    assert len(body) == 8000
    assert sender == "sender@example.com"
    assert sent_at == datetime.fromtimestamp(1712404800, tz=UTC)


def test_get_message_body_falls_back_to_html() -> None:
    service = _FakeService(
        _FakeMessagesAPI(
            message={
                "internalDate": "1712404800000",
                "payload": {
                    "headers": [{"name": "From", "value": "sender@example.com"}],
                    "parts": [
                        {
                            "mimeType": "text/html",
                            "body": {"data": _b64("<p>Hello <b>world</b></p>")},
                        },
                    ],
                },
            }
        )
    )

    body, _, _ = gmail.get_message_body(service, "m1")

    assert "Hello" in body
    assert "world" in body


def test_build_gmail_service_raises_gmail_reauth_required_on_invalid_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeCredentials:
        def __init__(self, **kwargs: object) -> None:
            self.token = kwargs.get("token")
            self.expiry = None
            self.expired = True

        def refresh(self, _request: object) -> None:
            raise RefreshError("invalid_grant")

    monkeypatch.setattr(gmail.crypto, "decrypt", lambda value: f"dec::{value}")
    monkeypatch.setattr(gmail, "Credentials", _FakeCredentials)
    monkeypatch.setattr(gmail, "_google_client_id", lambda: "client-id")
    monkeypatch.setattr(gmail, "_google_client_secret", lambda: "client-secret")

    with pytest.raises(gmail.GmailReauthRequired):
        gmail.build_gmail_service("enc-refresh", "enc-access", None)
