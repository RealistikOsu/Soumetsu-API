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
            """SELECT c.id, c.op as author_id, c.prof as profile_id,
                      c.msg as message, c.comment_date as created_at,
                      u.username as author_username
               FROM user_comments c
               INNER JOIN users u ON c.op = u.id
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
            """SELECT c.id, c.op as author_id, c.prof as profile_id,
                      c.msg as message, c.comment_date as created_at,
                      u.username as author_username
               FROM user_comments c
               INNER JOIN users u ON c.op = u.id
               WHERE c.prof = :profile_id
               ORDER BY c.comment_date DESC
               LIMIT :limit OFFSET :offset""",
            {"profile_id": profile_id, "limit": limit, "offset": offset},
        )
        return [CommentData(**row) for row in rows]

    async def create(
        self,
        author_id: int,
        profile_id: int,
        message: str,
        created_at: str,
    ) -> int:
        return await self._mysql.execute(
            """INSERT INTO user_comments (op, prof, msg, comment_date)
               VALUES (:author_id, :profile_id, :message, :created_at)""",
            {
                "author_id": author_id,
                "profile_id": profile_id,
                "message": message,
                "created_at": created_at,
            },
        )

    async def delete(self, comment_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM user_comments WHERE id = :comment_id",
            {"comment_id": comment_id},
        )

    async def find_author_id(self, comment_id: int) -> int | None:
        return await self._mysql.fetch_val(
            "SELECT op FROM user_comments WHERE id = :comment_id",
            {"comment_id": comment_id},
        )
