from __future__ import annotations

import time
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


_LOOKUP_TTL_SECONDS = 600
_FAILED_TTL_SECONDS = 60
_lookups: dict[str, tuple[float, DiscordUser | None]] = {}


async def lookup_user(discord_id: str) -> DiscordUser | None:
    """Looks up the current username and avatar of a Discord account by its id.

    People rename themselves on Discord all the time, so what was stored when they linked goes
    stale. Returns None when the lookup service can't be reached or doesn't know the account.
    """
    cached = _lookups.get(discord_id)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(
                f"{settings.DISCORD_USER_LOOKUP_URL}/{discord_id}",
            )
    except httpx.HTTPError:
        _lookups[discord_id] = (time.monotonic() + _FAILED_TTL_SECONDS, None)
        return None
    if response.status_code != 200:
        _lookups[discord_id] = (time.monotonic() + _FAILED_TTL_SECONDS, None)
        return None

    data = response.json()
    username = (data.get("raw") or {}).get("username") or data.get("username")
    if not username:
        _lookups[discord_id] = (time.monotonic() + _FAILED_TTL_SECONDS, None)
        return None

    avatar = data.get("avatar")
    user = DiscordUser(
        id=discord_id,
        username=username,
        avatar=(avatar.get("link") if isinstance(avatar, dict) else avatar) or "",
    )
    _lookups[discord_id] = (time.monotonic() + _LOOKUP_TTL_SECONDS, user)
    return user
