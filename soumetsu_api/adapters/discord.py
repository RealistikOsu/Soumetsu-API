from __future__ import annotations

from dataclasses import dataclass

import httpx

from soumetsu_api import settings

TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"


class DiscordOAuthError(Exception):
    pass


@dataclass
class DiscordUser:
    id: str
    username: str
    avatar: str


async def exchange_code(code: str, redirect_uri: str) -> str:
    """Exchanges an authorization code for an access token. Raises DiscordOAuthError on failure."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.DISCORD_APP_CLIENT_ID,
                "client_secret": settings.DISCORD_APP_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        raise DiscordOAuthError(f"token exchange failed: {response.status_code}")

    access_token = response.json().get("access_token")
    if not access_token:
        raise DiscordOAuthError("token exchange returned no access_token")

    return access_token


async def fetch_user(access_token: str) -> DiscordUser:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code != 200:
        raise DiscordOAuthError(f"user fetch failed: {response.status_code}")

    data = response.json()
    discord_id = data.get("id")
    if not discord_id:
        raise DiscordOAuthError("user fetch returned no id")

    return DiscordUser(
        id=discord_id,
        username=data.get("username", ""),
        avatar=data.get("avatar") or "",
    )
