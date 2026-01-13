from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class UserHistoryData(BaseModel):
    rank: int
    pp: int | None
    country_rank: int | None
    captured_at: str


class UserHistoryRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def get_history(
        self,
        user_id: int,
        mode: int,
        limit: int = 90,
    ) -> list[UserHistoryData]:
        rows = await self._mysql.fetch_all(
            """SELECT `rank`, pp, country_rank,
                      DATE_FORMAT(captured_at, '%%Y-%%m-%%d') as captured_at
               FROM user_profile_history
               WHERE user_id = :user_id
               AND mode = :mode
               ORDER BY captured_at DESC
               LIMIT :limit""",
            {"user_id": user_id, "mode": mode, "limit": limit},
        )
        return [UserHistoryData(**row) for row in rows]
