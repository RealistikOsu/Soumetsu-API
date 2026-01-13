from __future__ import annotations

import httpx

from soumetsu_api import settings

VERIFY_URL = "https://api.hcaptcha.com/siteverify"


async def verify_token(token: str, remote_ip: str | None = None) -> bool:
    if not settings.HCAPTCHA_ENABLED:
        return True

    if not settings.HCAPTCHA_SECRET_KEY:
        return True

    data = {
        "secret": settings.HCAPTCHA_SECRET_KEY,
        "response": token,
    }

    if remote_ip:
        data["remoteip"] = remote_ip

    async with httpx.AsyncClient() as client:
        response = await client.post(VERIFY_URL, data=data)

    if response.status_code != 200:
        return False

    result = response.json()
    return result.get("success", False)
