from __future__ import annotations

import time as time_module

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.constants import CustomMode

# Requests count against the limits for a rolling 24 hours, like the old API.
_DAY = 86400


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


class ProfileBeatmapSetData(BaseModel):
    beatmapset_id: int
    status: int
    time: int


class ProfileDifficultyData(BaseModel):
    beatmapset_id: int
    beatmap_id: int
    song_name: str
    mode: int
    status: int
    stars: float
    mapper_id: int
    mapper: str | None


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


# ranked = -1 marks a map the submission service reserved an ID for but that was never uploaded; it has
# no data and stays out of every lookup.
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
               FROM beatmaps WHERE beatmap_id = :beatmap_id AND ranked != -1""",
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
               FROM beatmaps WHERE beatmap_md5 = :beatmap_md5 AND ranked != -1""",
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
        conditions = ["ranked != -1"]
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
               FROM beatmaps WHERE beatmapset_id = :beatmapset_id AND ranked != -1
               ORDER BY difficulty_std ASC""",
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
        if custom_mode == CustomMode.LAZER:
            rows = await self._mysql.fetch_all(
                """SELECT b.beatmap_id, b.beatmapset_id, b.song_name, t.playcount
                   FROM (
                       SELECT beatmap_md5, COUNT(*) AS playcount
                       FROM lazer_scores
                       WHERE user_id = :user_id AND ruleset_id = :mode
                       GROUP BY beatmap_md5
                       ORDER BY playcount DESC
                       LIMIT :limit OFFSET :offset
                   ) t
                   INNER JOIN beatmaps b ON b.beatmap_md5 = t.beatmap_md5
                   ORDER BY t.playcount DESC""",
                {"user_id": user_id, "mode": mode, "limit": limit, "offset": offset},
            )
            return [MostPlayedBeatmapData(**row) for row in rows]

        scores_tables = ["scores", "scores_relax", "scores_ap"]
        scores_table = scores_tables[custom_mode]

        # Counting first and joining only the page's beatmaps keeps this fast. The "+ 0" stops MySQL from
        # intersecting the userid and play_mode indexes, which made it scan far more rows (over a second
        # for an active player) than walking that player's scores by userid alone.
        rows = await self._mysql.fetch_all(
            f"""SELECT b.beatmap_id, b.beatmapset_id, b.song_name, t.playcount
                FROM (
                    SELECT beatmap_md5, COUNT(*) AS playcount
                    FROM {scores_table}
                    WHERE userid = :user_id AND play_mode + 0 = :mode
                    GROUP BY beatmap_md5
                    ORDER BY playcount DESC
                    LIMIT :limit OFFSET :offset
                ) t
                INNER JOIN beatmaps b ON b.beatmap_md5 = t.beatmap_md5
                ORDER BY t.playcount DESC""",
            {"user_id": user_id, "mode": mode, "limit": limit, "offset": offset},
        )
        return [MostPlayedBeatmapData(**row) for row in rows]

    async def list_user_ranked_sets(
        self,
        user_id: int,
        limit: int,
        offset: int,
    ) -> list[ProfileBeatmapSetData]:
        # A difficulty only counts while it still has the status this user gave it.
        rows = await self._mysql.fetch_all(
            """SELECT b.beatmapset_id, MIN(r.status) AS status, MAX(r.ranked_at) AS time
               FROM beatmap_rankers r
               INNER JOIN beatmaps b ON b.beatmap_id = r.beatmap_id AND b.ranked = r.status
               WHERE r.user_id = :user_id
               GROUP BY b.beatmapset_id
               ORDER BY time DESC, b.beatmapset_id DESC
               LIMIT :limit OFFSET :offset""",
            {"user_id": user_id, "limit": limit, "offset": offset},
        )
        return [ProfileBeatmapSetData(**row) for row in rows]

    async def list_user_mapped_sets(
        self,
        user_id: int,
        limit: int,
        offset: int,
    ) -> list[ProfileBeatmapSetData]:
        # Only maps uploaded to this server have a mapper_id, and those all get set IDs from 1000000000 up,
        # which lets MySQL use the set index instead of scanning every beatmap.
        rows = await self._mysql.fetch_all(
            """SELECT beatmapset_id, MAX(ranked) AS status, MAX(latest_update) AS time
               FROM beatmaps
               WHERE beatmapset_id >= 1000000000 AND mapper_id = :user_id AND ranked != -1
               GROUP BY beatmapset_id
               ORDER BY time DESC, beatmapset_id DESC
               LIMIT :limit OFFSET :offset""",
            {"user_id": user_id, "limit": limit, "offset": offset},
        )
        return [ProfileBeatmapSetData(**row) for row in rows]

    async def list_set_difficulties(
        self,
        set_ids: list[int],
        ranked_by: int | None = None,
    ) -> list[ProfileDifficultyData]:
        if not set_ids:
            return []
        # For a ranker's list, only the difficulties they gave their current status to.
        ranker_join = (
            """INNER JOIN beatmap_rankers r ON r.beatmap_id = b.beatmap_id
                 AND r.user_id = :ranked_by AND b.ranked = r.status"""
            if ranked_by is not None
            else ""
        )
        placeholders = ", ".join(f":set_{i}" for i in range(len(set_ids)))
        params: dict[str, int] = {
            f"set_{i}": set_id for i, set_id in enumerate(set_ids)
        }
        if ranked_by is not None:
            params["ranked_by"] = ranked_by
        rows = await self._mysql.fetch_all(
            f"""SELECT b.beatmapset_id, b.beatmap_id, b.song_name, b.mode, b.ranked AS status,
                       CASE b.mode
                           WHEN 1 THEN b.difficulty_taiko
                           WHEN 2 THEN b.difficulty_ctb
                           WHEN 3 THEN b.difficulty_mania
                           ELSE b.difficulty_std
                       END AS stars,
                       b.mapper_id, u.username AS mapper
                FROM beatmaps b
                {ranker_join}
                LEFT JOIN users u ON u.id = b.mapper_id
                WHERE b.beatmapset_id IN ({placeholders})""",
            params,
        )
        return [ProfileDifficultyData(**row) for row in rows]

    async def count_recent_rank_requests(self) -> int:
        since = int(time_module.time()) - _DAY

        result = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM rank_requests
               WHERE blacklisted = 0 AND time >= :since""",
            {"since": since},
        )
        return result or 0

    async def count_user_recent_rank_requests(self, requester_id: int) -> int:
        since = int(time_module.time()) - _DAY

        result = await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM rank_requests
               WHERE userid = :requester_id AND time >= :since""",
            {"requester_id": requester_id, "since": since},
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
        queue_size: int,
    ) -> int | None:
        """Atomically create a rank request only if both the player and the queue are under their limits.

        Returns the request ID if created, None if the daily limit was reached.
        """
        requested_at = int(time_module.time())
        since = requested_at - _DAY

        await self._mysql.execute(
            """INSERT INTO rank_requests (userid, bid, type, time, blacklisted)
               SELECT :requester_id, :beatmap_id, :request_type, :requested_at, 0
               FROM dual
               WHERE (
                   SELECT COUNT(*) FROM rank_requests
                   WHERE userid = :requester_id AND time >= :since
               ) < :daily_limit
               AND (
                   SELECT COUNT(*) FROM rank_requests
                   WHERE blacklisted = 0 AND time >= :since
               ) < :queue_size""",
            {
                "requester_id": requester_id,
                "beatmap_id": beatmap_id,
                "request_type": request_type,
                "requested_at": requested_at,
                "since": since,
                "daily_limit": daily_limit,
                "queue_size": queue_size,
            },
        )

        # The driver reports 0 for an INSERT ... SELECT even when a row was written, so look it up.
        return await self._mysql.fetch_val(
            """SELECT id FROM rank_requests
               WHERE userid = :requester_id AND bid = :beatmap_id AND time = :requested_at""",
            {
                "requester_id": requester_id,
                "beatmap_id": beatmap_id,
                "requested_at": requested_at,
            },
        )

    async def find_user_oldest_recent_rank_request(
        self,
        requester_id: int,
    ) -> int | None:
        since = int(time_module.time()) - _DAY

        result = await self._mysql.fetch_val(
            """SELECT MIN(time) FROM rank_requests
               WHERE userid = :requester_id AND time >= :since""",
            {"requester_id": requester_id, "since": since},
        )
        return result

    async def list_pending_rank_requests(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RankRequestWithBeatmapData]:
        rows = await self._mysql.fetch_all(
            """SELECT
                r.id as request_id,
                r.type as request_type,
                r.time as requested_at,
                b.beatmap_id,
                b.beatmapset_id,
                b.song_name,
                b.ar,
                b.od,
                b.mode,
                b.difficulty_std,
                b.difficulty_taiko,
                b.difficulty_ctb,
                b.difficulty_mania,
                b.max_combo,
                b.hit_length,
                b.bpm,
                b.ranked,
                b.mapper_id
            FROM rank_requests r
            INNER JOIN beatmaps b ON (
                (r.type = 'b' AND b.beatmap_id = r.bid)
                OR (r.type = 's' AND b.beatmapset_id = r.bid)
            )
            WHERE r.blacklisted = 0
            ORDER BY r.time DESC, r.id DESC, b.difficulty_std ASC
            LIMIT :limit OFFSET :offset""",
            {"limit": limit, "offset": offset},
        )
        return [RankRequestWithBeatmapData(**row) for row in rows]

    async def count_pending_rank_requests(self) -> int:
        result = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM rank_requests WHERE blacklisted = 0",
        )
        return result or 0
