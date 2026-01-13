from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class FriendData(BaseModel):
    user_id: int
    username: str
    country: str


class FriendsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def get_friends(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FriendData]:
        rows = await self._mysql.fetch_all(
            """SELECT u.id as user_id, u.username, u.country
               FROM users_relationships r
               INNER JOIN users u ON r.user2 = u.id
               WHERE r.user1 = :user_id
               AND u.privileges & 1 = 1
               ORDER BY u.username ASC
               LIMIT :limit OFFSET :offset""",
            {"user_id": user_id, "limit": limit, "offset": offset},
        )
        return [FriendData(**row) for row in rows]

    async def get_followers(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FriendData]:
        rows = await self._mysql.fetch_all(
            """SELECT u.id as user_id, u.username, u.country
               FROM users_relationships r
               INNER JOIN users u ON r.user1 = u.id
               WHERE r.user2 = :user_id
               AND u.privileges & 1 = 1
               ORDER BY u.username ASC
               LIMIT :limit OFFSET :offset""",
            {"user_id": user_id, "limit": limit, "offset": offset},
        )
        return [FriendData(**row) for row in rows]

    async def is_friend(self, user_id: int, friend_id: int) -> bool:
        count = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM users_relationships
               WHERE user1 = :user_id AND user2 = :friend_id""",
            {"user_id": user_id, "friend_id": friend_id},
        )
        return count > 0

    async def add_friend(self, user_id: int, friend_id: int) -> None:
        await self._mysql.execute(
            """INSERT INTO users_relationships (user1, user2)
               VALUES (:user_id, :friend_id)""",
            {"user_id": user_id, "friend_id": friend_id},
        )

    async def remove_friend(self, user_id: int, friend_id: int) -> None:
        await self._mysql.execute(
            """DELETE FROM users_relationships
               WHERE user1 = :user_id AND user2 = :friend_id""",
            {"user_id": user_id, "friend_id": friend_id},
        )

    async def is_mutual(self, user_id: int, friend_id: int) -> bool:
        count = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM users_relationships r1
               INNER JOIN users_relationships r2
               ON r1.user1 = r2.user2 AND r1.user2 = r2.user1
               WHERE r1.user1 = :user_id AND r1.user2 = :friend_id""",
            {"user_id": user_id, "friend_id": friend_id},
        )
        return count > 0

    async def get_follower_count(self, user_id: int) -> int:
        count = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM users_relationships r
               INNER JOIN users u ON r.user1 = u.id
               WHERE r.user2 = :user_id AND u.privileges & 1 = 1""",
            {"user_id": user_id},
        )
        return count or 0

    async def get_friend_count(self, user_id: int) -> int:
        count = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM users_relationships r
               INNER JOIN users u ON r.user2 = u.id
               WHERE r.user1 = :user_id AND u.privileges & 1 = 1""",
            {"user_id": user_id},
        )
        return count or 0
