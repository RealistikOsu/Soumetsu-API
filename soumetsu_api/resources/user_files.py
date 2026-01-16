from __future__ import annotations

from soumetsu_api.adapters.storage import StorageAdapter


class UserFilesRepository:
    """Repository for user file operations (avatars, banners)."""

    __slots__ = ("_storage",)

    def __init__(self, storage: StorageAdapter) -> None:
        self._storage = storage

    async def save_avatar(self, user_id: int, image_data: bytes) -> str | None:
        return await self._storage.save_avatar(user_id, image_data)

    async def save_banner(self, user_id: int, image_data: bytes) -> str | None:
        return await self._storage.save_banner(user_id, image_data)

    async def delete_avatar(self, user_id: int) -> bool:
        return await self._storage.delete_avatar(user_id)

    async def delete_banner(self, user_id: int) -> bool:
        return await self._storage.delete_banner(user_id)
