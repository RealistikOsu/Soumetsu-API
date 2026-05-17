from __future__ import annotations

from pathlib import Path

from soumetsu_api.adapters.storage import StorageAdapter


class ClanFilesRepository:
    """Repository for clan file operations (icons)."""

    __slots__ = ("_storage",)

    def __init__(self, storage: StorageAdapter) -> None:
        self._storage = storage

    async def save_clan_icon(self, clan_id: int, image_data: bytes) -> str | None:
        return await self._storage.save_clan_icon(clan_id, image_data)

    async def delete_clan_icon(self, clan_id: int) -> bool:
        return await self._storage.delete_clan_icon(clan_id)

    def clan_icon_path(self, clan_id: int) -> Path:
        return self._storage.clan_icon_path(clan_id)
