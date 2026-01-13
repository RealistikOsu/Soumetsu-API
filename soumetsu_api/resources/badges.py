from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class BadgeData(BaseModel):
    id: int
    name: str
    icon: str


class BadgeMemberData(BaseModel):
    user_id: int
    username: str
    country: str


class BadgesRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def get_by_id(self, badge_id: int) -> BadgeData | None:
        row = await self._mysql.fetch_one(
            "SELECT id, name, icon FROM badges WHERE id = :badge_id",
            {"badge_id": badge_id},
        )
        if not row:
            return None

        return BadgeData(**row)

    async def get_all(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BadgeData]:
        rows = await self._mysql.fetch_all(
            """SELECT id, name, icon FROM badges
               ORDER BY id ASC
               LIMIT :limit OFFSET :offset""",
            {"limit": limit, "offset": offset},
        )
        return [BadgeData(**row) for row in rows]

    async def get_members(
        self,
        badge_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BadgeMemberData]:
        rows = await self._mysql.fetch_all(
            """SELECT u.id as user_id, u.username, u.country
               FROM users u
               INNER JOIN user_badges ub ON u.id = ub.user
               WHERE ub.badge = :badge_id
               AND u.privileges & 1 = 1
               ORDER BY u.username ASC
               LIMIT :limit OFFSET :offset""",
            {"badge_id": badge_id, "limit": limit, "offset": offset},
        )
        return [BadgeMemberData(**row) for row in rows]

    async def get_member_count(self, badge_id: int) -> int:
        result = await self._mysql.fetch_val(
            """SELECT COUNT(*)
               FROM user_badges ub
               INNER JOIN users u ON ub.user = u.id
               WHERE ub.badge = :badge_id
               AND u.privileges & 1 = 1""",
            {"badge_id": badge_id},
        )
        return result or 0
