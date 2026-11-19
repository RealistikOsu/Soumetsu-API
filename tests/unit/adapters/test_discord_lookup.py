from __future__ import annotations

import asyncio
import time

import pytest

from soumetsu_api.adapters import discord


@pytest.mark.asyncio
async def test_expired_lookup_is_served_stale_and_refreshed_in_background(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old = discord.DiscordUser(id="1", username="old", avatar="")
    new = discord.DiscordUser(id="1", username="new", avatar="")
    discord._lookups["1"] = (time.monotonic() - 1, old)
    release = asyncio.Event()

    async def slow_fetch(discord_id: str) -> discord.DiscordUser:
        await release.wait()
        discord._lookups[discord_id] = (time.monotonic() + 600, new)
        return new

    monkeypatch.setattr(discord, "_fetch_user", slow_fetch)

    assert await discord.lookup_user("1") == old

    release.set()
    await asyncio.gather(*discord._refreshing.values())
    assert await discord.lookup_user("1") == new


@pytest.mark.asyncio
async def test_lookup_is_skipped_without_a_service_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discord._lookups.pop("2", None)
    monkeypatch.setattr(discord.settings, "DISCORD_USER_LOOKUP_URL", "")

    assert await discord.lookup_user("2") is None
