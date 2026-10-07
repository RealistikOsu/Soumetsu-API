from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class DailyDayData(BaseModel):
    challenge_date: date
    placement: int
    stable_placement: int
    finalised: bool


class DailyStatsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def list_days(self, user_id: int) -> list[DailyDayData]:
        rows = await self._mysql.fetch_all(
            """SELECT challenge_date, placement, stable_placement, finalised
               FROM lazer_daily_challenge_days WHERE user_id = :user_id""",
            {"user_id": user_id},
        )
        return [DailyDayData(**row) for row in rows]
