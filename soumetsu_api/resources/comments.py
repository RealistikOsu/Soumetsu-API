from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class CommentData(BaseModel):
    id: int
    author_id: int
    profile_id: int
    message: str
    created_at: str
    author_username: str


class CommentsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def find_by_id(self, comment_id: int) -> CommentData | None:
        row = await self._mysql.fetch_one(
            """SELECT c.id, c.author_id, c.profile_id, c.message,
                      DATE_FORMAT(c.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at,
                      u.username as author_username
               FROM user_comments c
               INNER JOIN users u ON c.author_id = u.id
               WHERE c.id = :comment_id""",
            {"comment_id": comment_id},
        )
        if not row:
            return None

        return CommentData(**row)

    async def list_for_profile(
        self,
        profile_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CommentData]:
        rows = await self._mysql.fetch_all(
            """SELECT c.id, c.author_id, c.profile_id, c.message,
                      DATE_FORMAT(c.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at,
                      u.username as author_username
               FROM user_comments c
               INNER JOIN users u ON c.author_id = u.id
               WHERE c.profile_id = :profile_id
               ORDER BY c.created_at DESC
               LIMIT :limit OFFSET :offset""",
            {"profile_id": profile_id, "limit": limit, "offset": offset},
        )
        return [CommentData(**row) for row in rows]

    async def create(
        self,
        author_id: int,
        profile_id: int,
        message: str,
    ) -> int:
        # created_at defaults to CURRENT_TIMESTAMP in the clean schema.
        return await self._mysql.execute(
            """INSERT INTO user_comments (author_id, profile_id, message)
               VALUES (:author_id, :profile_id, :message)""",
            {
                "author_id": author_id,
                "profile_id": profile_id,
                "message": message,
            },
        )

    async def delete(self, comment_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM user_comments WHERE id = :comment_id",
            {"comment_id": comment_id},
        )

    async def find_author_id(self, comment_id: int) -> int | None:
        return await self._mysql.fetch_val(
            "SELECT author_id FROM user_comments WHERE id = :comment_id",
            {"comment_id": comment_id},
        )
