from __future__ import annotations

import time as time_module

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.constants import combined_mode

# Reconstruct the flat beatmap row the API expects from the split
# beatmapsets/beatmaps/beatmap_difficulty tables. song_name is composed;
# per-mode star ratings are pivoted from beatmap_difficulty.
_BEATMAP_SELECT = """
    b.id as beatmap_id, b.set_id as beatmapset_id, b.md5 as beatmap_md5,
    CONCAT(bs.artist, ' - ', bs.title, ' [', b.version, ']') as song_name,
    b.ar, b.od, b.mode,
    COALESCE(d0.stars, 0) as difficulty_std,
    COALESCE(d1.stars, 0) as difficulty_taiko,
    COALESCE(d2.stars, 0) as difficulty_ctb,
    COALESCE(d3.stars, 0) as difficulty_mania,
    b.max_combo, b.hit_length, CAST(b.bpm AS UNSIGNED) as bpm,
    b.playcount, b.passcount, b.status as ranked,
    COALESCE(UNIX_TIMESTAMP(bs.last_update), 0) as updated_at,
    b.status_frozen as ranked_status_frozen, COALESCE(bs.mapper_id, 0) as mapper_id
"""

_BEATMAP_FROM = """
    FROM beatmaps b
    INNER JOIN beatmapsets bs ON b.set_id = bs.id
    LEFT JOIN beatmap_difficulty d0 ON d0.beatmap_id = b.id AND d0.mode = 0
    LEFT JOIN beatmap_difficulty d1 ON d1.beatmap_id = b.id AND d1.mode = 1
    LEFT JOIN beatmap_difficulty d2 ON d2.beatmap_id = b.id AND d2.mode = 2
    LEFT JOIN beatmap_difficulty d3 ON d3.beatmap_id = b.id AND d3.mode = 3
"""


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


class RankRequestWithBeatmapData(BaseModel):
    request_id: int
    request_type: str
    requested_at: int
    beatmap_id: int
    beatmapset_id: int
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
    ranked: int
    mapper_id: int


class BeatmapsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def find_by_id(self, beatmap_id: int) -> BeatmapData | None:
        row = await self._mysql.fetch_one(
            f"""SELECT {_BEATMAP_SELECT}
                {_BEATMAP_FROM}
                WHERE b.id = :beatmap_id""",
            {"beatmap_id": beatmap_id},
        )
        if not row:
            return None

        return BeatmapData(**row)

    async def find_by_md5(self, beatmap_md5: str) -> BeatmapData | None:
        row = await self._mysql.fetch_one(
            f"""SELECT {_BEATMAP_SELECT}
                {_BEATMAP_FROM}
                WHERE b.md5 = :beatmap_md5""",
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
            conditions.append(
                "CONCAT(bs.artist, ' - ', bs.title, ' [', b.version, ']') LIKE :query",
            )
            params["query"] = f"%{query}%"

        if mode is not None:
            conditions.append("b.mode = :mode")
            params["mode"] = mode

        if status is not None:
            conditions.append("b.status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        rows = await self._mysql.fetch_all(
            f"""SELECT {_BEATMAP_SELECT}
                {_BEATMAP_FROM}
                WHERE {where_clause}
                ORDER BY b.playcount DESC
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
        conditions = ["b.status IN (2, 3, 4, 5)"]
        params: dict[str, int] = {"limit": limit, "offset": offset}

        if mode is not None:
            conditions.append("b.mode = :mode")
            params["mode"] = mode

        where_clause = " AND ".join(conditions)

        rows = await self._mysql.fetch_all(
            f"""SELECT {_BEATMAP_SELECT}
                {_BEATMAP_FROM}
                WHERE {where_clause}
                ORDER BY b.playcount DESC
                LIMIT :limit OFFSET :offset""",
            params,
        )
        return [BeatmapData(**row) for row in rows]

    async def list_beatmapset(
        self,
        beatmapset_id: int,
    ) -> list[BeatmapData]:
        rows = await self._mysql.fetch_all(
            f"""SELECT {_BEATMAP_SELECT}
                {_BEATMAP_FROM}
                WHERE b.set_id = :beatmapset_id
                ORDER BY COALESCE(d0.stars, 0) ASC""",
            {"beatmapset_id": beatmapset_id},
        )
        return [BeatmapData(**row) for row in rows]

    async def get_user_most_played(
        self,
        user_id: int,
        mode: int,
        custom_mode: int,
        limit: int = 5,
        offset: int = 0,
    ) -> list[MostPlayedBeatmapData]:
        cmode = combined_mode(mode, custom_mode)

        rows = await self._mysql.fetch_all(
            """SELECT b.id as beatmap_id, b.set_id as beatmapset_id,
                      CONCAT(bs.artist, ' - ', bs.title, ' [', b.version, ']') as song_name,
                      COUNT(*) as playcount
               FROM scores s
               INNER JOIN beatmaps b ON s.beatmap_md5 = b.md5
               INNER JOIN beatmapsets bs ON b.set_id = bs.id
               WHERE s.user_id = :user_id
               AND s.mode = :cmode
               GROUP BY s.beatmap_md5
               ORDER BY playcount DESC
               LIMIT :limit OFFSET :offset""",
            {"user_id": user_id, "cmode": cmode, "limit": limit, "offset": offset},
        )
        return [MostPlayedBeatmapData(**row) for row in rows]

    async def count_rank_requests_today(self) -> int:
        today_start = int(time_module.time()) - (int(time_module.time()) % 86400)

        result = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM rank_requests
               WHERE blacklisted = 0 AND requested_at >= FROM_UNIXTIME(:today_start)""",
            {"today_start": today_start},
        )
        return result or 0

    async def count_user_rank_requests_today(self, requester_id: int) -> int:
        today_start = int(time_module.time()) - (int(time_module.time()) % 86400)

        result = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM rank_requests
               WHERE user_id = :requester_id
               AND requested_at >= FROM_UNIXTIME(:today_start)""",
            {"requester_id": requester_id, "today_start": today_start},
        )
        return result or 0

    async def find_rank_request_by_beatmap(
        self,
        beatmap_id: int,
        request_type: str,
    ) -> RankRequestData | None:
        row = await self._mysql.fetch_one(
            """SELECT id, user_id as requester_id, beatmap_id,
                      type as request_type,
                      UNIX_TIMESTAMP(requested_at) as requested_at, blacklisted
               FROM rank_requests
               WHERE beatmap_id = :beatmap_id AND type = :request_type""",
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
        await self._mysql.execute(
            """INSERT INTO rank_requests (user_id, beatmap_id, type, blacklisted)
               VALUES (:requester_id, :beatmap_id, :request_type, 0)""",
            {
                "requester_id": requester_id,
                "beatmap_id": beatmap_id,
                "request_type": request_type,
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
            """INSERT INTO rank_requests (user_id, beatmap_id, type, blacklisted)
               SELECT :requester_id, :beatmap_id, :request_type, 0
               FROM dual
               WHERE (
                   SELECT COUNT(*) FROM (
                       SELECT id FROM rank_requests
                       WHERE user_id = :requester_id
                       AND requested_at >= FROM_UNIXTIME(:today_start)
                   ) AS todays_requests
               ) < :daily_limit""",
            {
                "requester_id": requester_id,
                "beatmap_id": beatmap_id,
                "request_type": request_type,
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
            """SELECT UNIX_TIMESTAMP(MIN(requested_at)) FROM rank_requests
               WHERE user_id = :requester_id
               AND requested_at >= FROM_UNIXTIME(:today_start)""",
            {"requester_id": requester_id, "today_start": today_start},
        )
        return result

    async def list_pending_rank_requests(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RankRequestWithBeatmapData]:
        rows = await self._mysql.fetch_all(
            f"""SELECT
                r.id as request_id,
                r.type as request_type,
                UNIX_TIMESTAMP(r.requested_at) as requested_at,
                b.id as beatmap_id,
                b.set_id as beatmapset_id,
                CONCAT(bs.artist, ' - ', bs.title, ' [', b.version, ']') as song_name,
                b.ar,
                b.od,
                b.mode,
                COALESCE(d0.stars, 0) as difficulty_std,
                COALESCE(d1.stars, 0) as difficulty_taiko,
                COALESCE(d2.stars, 0) as difficulty_ctb,
                COALESCE(d3.stars, 0) as difficulty_mania,
                b.max_combo,
                b.hit_length,
                CAST(b.bpm AS UNSIGNED) as bpm,
                b.status as ranked,
                COALESCE(bs.mapper_id, 0) as mapper_id
            FROM rank_requests r
            INNER JOIN beatmaps b ON (
                (r.type = 'b' AND b.id = r.beatmap_id)
                OR (r.type = 's' AND b.set_id = r.beatmap_id)
            )
            INNER JOIN beatmapsets bs ON b.set_id = bs.id
            LEFT JOIN beatmap_difficulty d0 ON d0.beatmap_id = b.id AND d0.mode = 0
            LEFT JOIN beatmap_difficulty d1 ON d1.beatmap_id = b.id AND d1.mode = 1
            LEFT JOIN beatmap_difficulty d2 ON d2.beatmap_id = b.id AND d2.mode = 2
            LEFT JOIN beatmap_difficulty d3 ON d3.beatmap_id = b.id AND d3.mode = 3
            WHERE r.blacklisted = 0
            ORDER BY r.requested_at DESC, r.id DESC, COALESCE(d0.stars, 0) ASC
            LIMIT :limit OFFSET :offset""",
            {"limit": limit, "offset": offset},
        )
        return [RankRequestWithBeatmapData(**row) for row in rows]

    async def count_pending_rank_requests(self) -> int:
        result = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM rank_requests WHERE blacklisted = 0",
        )
        return result or 0
