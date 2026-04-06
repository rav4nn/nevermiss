from __future__ import annotations

import resend

from app.config import get_settings

FROM_ADDRESS = "NeverMiss <digest@nevermiss.my>"


def send_email(to: str, subject: str, html: str, text: str) -> None:
    resend.api_key = get_settings().resend_api_key
    resend.Emails.send(
        {
            "from": FROM_ADDRESS,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
        }
    )
