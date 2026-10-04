from __future__ import annotations

from email.utils import parseaddr

import httpx

from soumetsu_api import settings


class MailError(Exception):
    pass


async def send(to: str, subject: str, html: str) -> None:
    name, sender = parseaddr(settings.MAIL_FROM)
    if not settings.BREVO_API_KEY or not sender:
        raise MailError("Brevo is not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": settings.BREVO_API_KEY},
            json={
                "sender": {"email": sender, "name": name or "RealistikOsu"},
                "to": [{"email": to}],
                "subject": subject,
                "htmlContent": html,
            },
        )
    if response.status_code >= 400:
        raise MailError(f"Brevo returned {response.status_code}")
