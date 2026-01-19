from __future__ import annotations

import time as time_module

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class BeatmapData(BaseModel):
    beatmap_id: int
    beatmapset_id: int
    beatmap_md5: str
    song_name: str
    ar: float
    od: float
    mode: int
    difficulty_std: float
    difficulty_taiko: float
    difficulty_ctb: float
    difficulty_mania: float
    max_combo: int
    hit_length: int
    bpm: int
    playcount: int
    passcount: int
    ranked: int
    updated_at: int
    ranked_status_frozen: bool
    mapper_id: int


class MostPlayedBeatmapData(BaseModel):
    beatmap_id: int
    beatmapset_id: int
    song_name: str
    playcount: int


class RankRequestData(BaseModel):
    id: int
    requester_id: int
    beatmap_id: int
    request_type: str
    requested_at: int
    blacklisted: bool


class BeatmapsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def find_by_id(self, beatmap_id: int) -> BeatmapData | None:
        row = await self._mysql.fetch_one(
            """SELECT beatmap_id, beatmapset_id, beatmap_md5, song_name,
                      ar, od, mode, difficulty_std, difficulty_taiko,
                      difficulty_ctb, difficulty_mania, max_combo,
                      hit_length, bpm, playcount, passcount, ranked,
                      latest_update as updated_at,
                      ranked_status_freezed as ranked_status_frozen, mapper_id
               FROM beatmaps WHERE beatmap_id = :beatmap_id""",
            {"beatmap_id": beatmap_id},
        )
        if not row:
            return None

        return BeatmapData(**row)

    async def find_by_md5(self, beatmap_md5: str) -> BeatmapData | None:
        row = await self._mysql.fetch_one(
            """SELECT beatmap_id, beatmapset_id, beatmap_md5, song_name,
                      ar, od, mode, difficulty_std, difficulty_taiko,
                      difficulty_ctb, difficulty_mania, max_combo,
                      hit_length, bpm, playcount, passcount, ranked,
                      latest_update as updated_at,
                      ranked_status_freezed as ranked_status_frozen, mapper_id
               FROM beatmaps WHERE beatmap_md5 = :beatmap_md5""",
            {"beatmap_md5": beatmap_md5},
        )
        if not row:
            return None

        return BeatmapData(**row)

    async def search(
        self,
        query: str | None = None,
        mode: int | None = None,
        status: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BeatmapData]:
        conditions = []
        params: dict[str, str | int] = {"limit": limit, "offset": offset}

        if query:
            conditions.append("song_name LIKE :query")
            params["query"] = f"%{query}%"

        if mode is not None:
            conditions.append("mode = :mode")
            params["mode"] = mode

        if status is not None:
            conditions.append("ranked = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        rows = await self._mysql.fetch_all(
            f"""SELECT beatmap_id, beatmapset_id, beatmap_md5, song_name,
                       ar, od, mode, difficulty_std, difficulty_taiko,
                       difficulty_ctb, difficulty_mania, max_combo,
                       hit_length, bpm, playcount, passcount, ranked,
                       latest_update as updated_at,
                       ranked_status_freezed as ranked_status_frozen, mapper_id
                FROM beatmaps
                WHERE {where_clause}
                ORDER BY playcount DESC
                LIMIT :limit OFFSET :offset""",
            params,
        )
        return [BeatmapData(**row) for row in rows]

    async def list_popular(
        self,
        mode: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BeatmapData]:
        conditions = ["ranked IN (2, 3, 4, 5)"]
        params: dict[str, int] = {"limit": limit, "offset": offset}

        if mode is not None:
            conditions.append("mode = :mode")
            params["mode"] = mode

        where_clause = " AND ".join(conditions)

        rows = await self._mysql.fetch_all(
            f"""SELECT beatmap_id, beatmapset_id, beatmap_md5, song_name,
                       ar, od, mode, difficulty_std, difficulty_taiko,
                       difficulty_ctb, difficulty_mania, max_combo,
                       hit_length, bpm, playcount, passcount, ranked,
                       latest_update as updated_at,
                       ranked_status_freezed as ranked_status_frozen, mapper_id
                FROM beatmaps
                WHERE {where_clause}
                ORDER BY playcount DESC
                LIMIT :limit OFFSET :offset""",
            params,
        )
        return [BeatmapData(**row) for row in rows]

    async def list_beatmapset(
        self,
        beatmapset_id: int,
    ) -> list[BeatmapData]:
        rows = await self._mysql.fetch_all(
            """SELECT beatmap_id, beatmapset_id, beatmap_md5, song_name,
                      ar, od, mode, difficulty_std, difficulty_taiko,
                      difficulty_ctb, difficulty_mania, max_combo,
                      hit_length, bpm, playcount, passcount, ranked,
                      latest_update as updated_at,
                      ranked_status_freezed as ranked_status_frozen, mapper_id
               FROM beatmaps WHERE beatmapset_id = :beatmapset_id
               ORDER BY difficulty_std ASC""",
            {"beatmapset_id": beatmapset_id},
        )
        return [BeatmapData(**row) for row in rows]

    async def get_user_most_played(
        self,
        user_id: int,
        mode: int,
        playstyle: int,
        limit: int = 5,
        offset: int = 0,
    ) -> list[MostPlayedBeatmapData]:
        # Select table based on playstyle
        scores_tables = ["scores", "scores_relax", "scores_ap"]
        scores_table = scores_tables[playstyle]

        rows = await self._mysql.fetch_all(
            f"""SELECT b.beatmap_id, b.beatmapset_id, b.song_name,
                       COUNT(*) as playcount
                FROM {scores_table} s
                INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
                WHERE s.userid = :user_id
                AND s.play_mode = :mode
                GROUP BY s.beatmap_md5
                ORDER BY playcount DESC
                LIMIT :limit OFFSET :offset""",
            {"user_id": user_id, "mode": mode, "limit": limit, "offset": offset},
        )
        return [MostPlayedBeatmapData(**row) for row in rows]

    async def count_rank_requests_today(self) -> int:
        today_start = int(time_module.time()) - (int(time_module.time()) % 86400)

        result = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM rank_requests
               WHERE blacklisted = 0 AND time >= :today_start""",
            {"today_start": today_start},
        )
        return result or 0

    async def count_user_rank_requests_today(self, requester_id: int) -> int:
        today_start = int(time_module.time()) - (int(time_module.time()) % 86400)

        result = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM rank_requests
               WHERE userid = :requester_id AND time >= :today_start""",
            {"requester_id": requester_id, "today_start": today_start},
        )
        return result or 0

    async def find_rank_request_by_beatmap(
        self,
        beatmap_id: int,
        request_type: str,
    ) -> RankRequestData | None:
        row = await self._mysql.fetch_one(
            """SELECT id, userid as requester_id, bid as beatmap_id,
                      type as request_type, time as requested_at, blacklisted
               FROM rank_requests
               WHERE bid = :beatmap_id AND type = :request_type""",
            {"beatmap_id": beatmap_id, "request_type": request_type},
        )
        if not row:
            return None
        return RankRequestData(**row)

    async def create_rank_request(
        self,
        requester_id: int,
        beatmap_id: int,
        request_type: str,
    ) -> int:
        requested_at = int(time_module.time())
        await self._mysql.execute(
            """INSERT INTO rank_requests (userid, bid, type, time, blacklisted)
               VALUES (:requester_id, :beatmap_id, :request_type, :requested_at, 0)""",
            {
                "requester_id": requester_id,
                "beatmap_id": beatmap_id,
                "request_type": request_type,
                "requested_at": requested_at,
            },
        )
        result = await self._mysql.fetch_val("SELECT LAST_INSERT_ID()")
        return result or 0

    async def create_rank_request_with_atomic_limit(
        self,
        requester_id: int,
        beatmap_id: int,
        request_type: str,
        daily_limit: int,
    ) -> int | None:
        """Atomically create a rank request only if the user is below the daily limit.

        Returns the request ID if created, None if the daily limit was reached.
        """
        requested_at = int(time_module.time())
        today_start = requested_at - (requested_at % 86400)

        result = await self._mysql.execute(
            """INSERT INTO rank_requests (userid, bid, type, time, blacklisted)
               SELECT :requester_id, :beatmap_id, :request_type, :requested_at, 0
               FROM dual
               WHERE (
                   SELECT COUNT(*) FROM rank_requests
                   WHERE userid = :requester_id AND time >= :today_start
               ) < :daily_limit""",
            {
                "requester_id": requester_id,
                "beatmap_id": beatmap_id,
                "request_type": request_type,
                "requested_at": requested_at,
                "today_start": today_start,
                "daily_limit": daily_limit,
            },
        )

        if result == 0:
            return None

        request_id = await self._mysql.fetch_val("SELECT LAST_INSERT_ID()")
        return request_id or None

    async def find_user_oldest_rank_request_today(
        self,
        requester_id: int,
    ) -> int | None:
        today_start = int(time_module.time()) - (int(time_module.time()) % 86400)

        result = await self._mysql.fetch_val(
            """SELECT MIN(time) FROM rank_requests
               WHERE userid = :requester_id AND time >= :today_start""",
            {"requester_id": requester_id, "today_start": today_start},
        )
        return result
