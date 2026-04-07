from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from google import genai
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.core import crypto
from app.core.db import ConfidenceLevel, DateType, ItemCategory
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger("integrations.gemini")
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "extraction.txt"


@dataclass
class LLMExtraction:
    name: str
    category: ItemCategory
    date: date
    date_type: DateType
    confidence: ConfidenceLevel
    notes: str


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _select_api_key(user: User) -> str:
    if user.api_key_enc:
        return crypto.decrypt(user.api_key_enc)
    return get_settings().gemini_api_key


def _build_prompt(email_body: str, sender: str, sent_at: datetime) -> str:
    sent_at_utc = sent_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return (
        f"{_load_prompt()}\n\n"
        f"Sender: {sender}\n"
        f"Sent At: {sent_at_utc}\n"
        f"Email Body:\n{email_body}"
    )


@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _generate_content(api_key: str, prompt: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    text = response.text
    if not isinstance(text, str):
        raise ValueError("Gemini response did not contain text output.")
    return text


def _parse_extractions(raw_text: str) -> list[LLMExtraction]:
    parsed = json.loads(raw_text)
    if not isinstance(parsed, list):
        raise ValueError("Gemini response was not a JSON array.")

    extractions: list[LLMExtraction] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("Gemini extraction item was not an object.")
        extractions.append(
            LLMExtraction(
                name=str(item["name"]).strip(),
                category=ItemCategory(item["category"]),
                date=date.fromisoformat(str(item["date"])),
                date_type=DateType(item["date_type"]),
                confidence=ConfidenceLevel(item["confidence"]),
                notes=str(item.get("notes", "")),
            )
        )
    return extractions


def _has_explicit_date_string(email_body: str, extracted_date: date) -> bool:
    lowered = email_body.lower()
    candidates = {
        extracted_date.isoformat(),
        extracted_date.strftime("%Y/%m/%d"),
        extracted_date.strftime("%d/%m/%Y"),
        extracted_date.strftime("%m/%d/%Y"),
        extracted_date.strftime("%b %d %Y").lower(),
        extracted_date.strftime("%B %d %Y").lower(),
        extracted_date.strftime("%b %d, %Y").lower(),
        extracted_date.strftime("%B %d, %Y").lower(),
    }
    return any(candidate in lowered for candidate in candidates)


def _post_filter(email_body: str, items: list[LLMExtraction]) -> list[LLMExtraction]:
    cutoff = datetime.now(UTC).date() - timedelta(days=90)
    filtered: list[LLMExtraction] = []
    for item in items:
        if item.date < cutoff:
            continue
        if item.confidence == ConfidenceLevel.LOW and not _has_explicit_date_string(
            email_body,
            item.date,
        ):
            continue
        filtered.append(item)
    return filtered


def extract_items(
    email_body: str,
    sender: str,
    sent_at: datetime,
    user: User,
) -> list[LLMExtraction]:
    api_key = _select_api_key(user)
    prompt = _build_prompt(email_body, sender, sent_at)

    try:
        raw_text = _generate_content(api_key, prompt)
        parsed = _parse_extractions(raw_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "gemini_extraction_parse_failed",
            sender=sender,
            error_type=type(exc).__name__,
        )
        return []

    return _post_filter(email_body, parsed)
