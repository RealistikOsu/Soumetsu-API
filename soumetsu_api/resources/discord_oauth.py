from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class DiscordOAuthData(BaseModel):
    discord_id: str
    discord_username: str
    discord_avatar: str


class DiscordOAuthRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def get_by_user(self, user_id: int) -> DiscordOAuthData | None:
        row = await self._mysql.fetch_one(
            """SELECT discord_id, discord_username, discord_avatar
               FROM discord_oauth WHERE user_id = :user_id LIMIT 1""",
            {"user_id": user_id},
        )
        if not row:
            return None
        return DiscordOAuthData(
            discord_id=row["discord_id"],
            discord_username=row["discord_username"],
            discord_avatar=row["discord_avatar"],
        )

    async def get_user_for_discord(self, discord_id: str) -> int | None:
        return await self._mysql.fetch_val(
            "SELECT user_id FROM discord_oauth WHERE discord_id = :discord_id LIMIT 1",
            {"discord_id": discord_id},
        )

    async def delete_by_user(self, user_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM discord_oauth WHERE user_id = :user_id",
            {"user_id": user_id},
        )

    async def insert(
        self,
        user_id: int,
        discord_id: str,
        discord_username: str,
        discord_avatar: str,
    ) -> None:
        await self._mysql.execute(
            """INSERT INTO discord_oauth (user_id, discord_id, discord_username, discord_avatar)
               VALUES (:user_id, :discord_id, :discord_username, :discord_avatar)""",
            {
                "user_id": user_id,
                "discord_id": discord_id,
                "discord_username": discord_username,
                "discord_avatar": discord_avatar,
            },
        )
