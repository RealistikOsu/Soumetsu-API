from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class CommentData(BaseModel):
    id: int
    op: int
    prof: int
    msg: str
    comment_date: str
    op_username: str


class CommentsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def get_by_id(self, comment_id: int) -> CommentData | None:
        row = await self._mysql.fetch_one(
            """SELECT c.id, c.op, c.prof, c.msg, c.comment_date,
                      u.username as op_username
               FROM user_comments c
               INNER JOIN users u ON c.op = u.id
               WHERE c.id = :comment_id""",
            {"comment_id": comment_id},
        )
        if not row:
            return None

        return CommentData(**row)

    async def get_for_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CommentData]:
        rows = await self._mysql.fetch_all(
            """SELECT c.id, c.op, c.prof, c.msg, c.comment_date,
                      u.username as op_username
               FROM user_comments c
               INNER JOIN users u ON c.op = u.id
               WHERE c.prof = :user_id
               ORDER BY c.comment_date DESC
               LIMIT :limit OFFSET :offset""",
            {"user_id": user_id, "limit": limit, "offset": offset},
        )
        return [CommentData(**row) for row in rows]

    async def create(
        self,
        op: int,
        prof: int,
        msg: str,
        comment_date: str,
    ) -> int:
        return await self._mysql.execute(
            """INSERT INTO user_comments (op, prof, msg, comment_date)
               VALUES (:op, :prof, :msg, :comment_date)""",
            {"op": op, "prof": prof, "msg": msg, "comment_date": comment_date},
        )

    async def delete(self, comment_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM user_comments WHERE id = :comment_id",
            {"comment_id": comment_id},
        )

    async def get_owner(self, comment_id: int) -> int | None:
        return await self._mysql.fetch_val(
            "SELECT op FROM user_comments WHERE id = :comment_id",
            {"comment_id": comment_id},
        )
