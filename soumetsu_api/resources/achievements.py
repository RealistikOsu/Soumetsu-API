from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class AchievementData(BaseModel):
    id: int
    name: str
    description: str
    file: str


class UserAchievementData(BaseModel):
    achievement_id: int
    time: int


class AchievementsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def get_all(self) -> list[AchievementData]:
        rows = await self._mysql.fetch_all(
            """SELECT id, name, description, file
               FROM achievements
               ORDER BY id ASC""",
            {},
        )
        return [AchievementData(**row) for row in rows]

    async def get_user_achievements(
        self,
        user_id: int,
    ) -> list[UserAchievementData]:
        rows = await self._mysql.fetch_all(
            """SELECT achievement_id, UNIX_TIMESTAMP(unlocked_at) as time
               FROM user_achievements
               WHERE user_id = :user_id
               ORDER BY achievement_id ASC""",
            {"user_id": user_id},
        )
        return [UserAchievementData(**row) for row in rows]
