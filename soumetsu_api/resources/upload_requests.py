from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class UploadRequestData(BaseModel):
    id: int
    user_id: int
    username: str
    country: str
    score_id: int
    custom_mode: int
    skin_url: str
    reason: str
    status: int
    created_at: int
    up: int
    down: int
    mine: int


class UploadRequestsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def list_by_status(
        self,
        status: int,
        viewer_id: int,
        limit: int,
        offset: int,
    ) -> list[UploadRequestData]:
        rows = await self._mysql.fetch_all(
            """SELECT r.id, r.user_id, u.username, u.country, r.score_id, r.custom_mode,
                      r.skin_url, r.reason, r.status, r.created_at,
                      (SELECT COUNT(*) FROM upload_request_votes v
                       WHERE v.request_id = r.id AND v.vote = 1) AS up,
                      (SELECT COUNT(*) FROM upload_request_votes v
                       WHERE v.request_id = r.id AND v.vote = -1) AS down,
                      COALESCE((SELECT v.vote FROM upload_request_votes v
                                WHERE v.request_id = r.id AND v.user_id = :viewer_id), 0) AS mine
               FROM upload_requests r
               INNER JOIN users u ON u.id = r.user_id
               WHERE r.status = :status
               ORDER BY r.id DESC
               LIMIT :limit OFFSET :offset""",
            {
                "status": status,
                "viewer_id": viewer_id,
                "limit": limit,
                "offset": offset,
            },
        )
        return [UploadRequestData(**row) for row in rows]

    async def count_by_status(self, status: int) -> int:
        return await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM upload_requests WHERE status = :status",
            {"status": status},
        )

    async def count_open_for_user(self, user_id: int) -> int:
        return await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM upload_requests WHERE user_id = :user_id AND status = 0",
            {"user_id": user_id},
        )

    async def find_owner_and_status(self, request_id: int) -> tuple[int, int] | None:
        row = await self._mysql.fetch_one(
            "SELECT user_id, status FROM upload_requests WHERE id = :request_id",
            {"request_id": request_id},
        )
        return (row["user_id"], row["status"]) if row else None

    async def create(
        self,
        user_id: int,
        score_id: int,
        custom_mode: int,
        skin_url: str,
        reason: str,
        created_at: int,
    ) -> int:
        return await self._mysql.execute(
            """INSERT INTO upload_requests
                   (user_id, score_id, custom_mode, skin_url, reason, created_at)
               VALUES (:user_id, :score_id, :custom_mode, :skin_url, :reason, :created_at)""",
            {
                "user_id": user_id,
                "score_id": score_id,
                "custom_mode": custom_mode,
                "skin_url": skin_url,
                "reason": reason,
                "created_at": created_at,
            },
        )

    async def delete(self, request_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM upload_requests WHERE id = :request_id",
            {"request_id": request_id},
        )

    async def set_vote(self, request_id: int, user_id: int, vote: int) -> None:
        await self._mysql.execute(
            """INSERT INTO upload_request_votes (request_id, user_id, vote)
               VALUES (:request_id, :user_id, :vote)
               ON DUPLICATE KEY UPDATE vote = VALUES(vote)""",
            {"request_id": request_id, "user_id": user_id, "vote": vote},
        )

    async def clear_vote(self, request_id: int, user_id: int) -> None:
        await self._mysql.execute(
            """DELETE FROM upload_request_votes
               WHERE request_id = :request_id AND user_id = :user_id""",
            {"request_id": request_id, "user_id": user_id},
        )

    async def vote_counts(self, request_id: int) -> tuple[int, int]:
        row = await self._mysql.fetch_one(
            """SELECT CAST(COALESCE(SUM(vote = 1), 0) AS SIGNED) AS up,
                      CAST(COALESCE(SUM(vote = -1), 0) AS SIGNED) AS down
               FROM upload_request_votes WHERE request_id = :request_id""",
            {"request_id": request_id},
        )
        return row["up"], row["down"]

    async def set_status(
        self,
        request_id: int,
        status: int,
        reviewed_by: int | None,
        reviewed_at: int | None,
    ) -> None:
        await self._mysql.execute(
            """UPDATE upload_requests
               SET status = :status, reviewed_by = :reviewed_by, reviewed_at = :reviewed_at
               WHERE id = :request_id""",
            {
                "request_id": request_id,
                "status": status,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
            },
        )
