from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.adapters.redis import RedisClient
from soumetsu_api.constants import get_mode_suffix
from soumetsu_api.constants import get_stats_table

LEADERBOARD_KEY_PREFIX = "leaderboard"


class LeaderboardModeStats(BaseModel):
    pp: int
    accuracy: float
    playcount: int
    level: float


class LeaderboardEntry(BaseModel):
    id: int
    username: str
    country: str
    privileges: int
    chosen_mode: LeaderboardModeStats
    global_rank: int
    country_rank: int


class FirstPlaceEntry(BaseModel):
    player_id: int
    username: str
    score_id: int
    beatmap_md5: str
    song_name: str
    pp: float
    achieved_at: int
    mode: int


def _build_leaderboard_key(
    custom_mode: int,
    mode: int,
    country: str | None = None,
) -> str:
    suffix = get_mode_suffix(mode)
    custom_mode_names = {0: "vanilla", 1: "relax", 2: "autopilot"}
    custom_mode_name = custom_mode_names.get(custom_mode, "vanilla")

    if country:
        return f"{LEADERBOARD_KEY_PREFIX}:{custom_mode_name}:{suffix}:{country.lower()}"
    return f"{LEADERBOARD_KEY_PREFIX}:{custom_mode_name}:{suffix}"


def _calculate_level(total_score: int) -> float:
    if total_score <= 0:
        return 1.0

    level = 1
    score_req = 0

    while score_req <= total_score:
        level += 1
        if level <= 100:
            score_req += (
                5000 // 3 * (4 * (level**3) - 3 * (level**2) - level)
                + 1250 * (1.8 ** (level - 60)) // 3
            )
        else:
            score_req += 26931190829 + 100000000000 * (level - 100)

        if level > 120:
            break

    progress = 0.0
    if level > 1:
        prev_req = 0
        for lv in range(2, level):
            if lv <= 100:
                prev_req += (
                    5000 // 3 * (4 * (lv**3) - 3 * (lv**2) - lv)
                    + 1250 * (1.8 ** (lv - 60)) // 3
                )
            else:
                prev_req += 26931190829 + 100000000000 * (lv - 100)

        if score_req > prev_req:
            progress = (total_score - prev_req) / (score_req - prev_req)

    return float(level - 1) + progress


class LeaderboardRepository:
    __slots__ = ("_mysql", "_redis")

    def __init__(self, mysql: ImplementsMySQL, redis: RedisClient) -> None:
        self._mysql = mysql
        self._redis = redis

    async def get_global(
        self,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LeaderboardEntry]:
        key = _build_leaderboard_key(custom_mode, mode)
        user_ids = await self._redis.zrevrange(key, offset, offset + limit - 1)

        if not user_ids:
            return []

        return await self._fetch_users_with_ranks(
            user_ids,
            mode,
            custom_mode,
            offset,
        )

    async def get_country(
        self,
        country: str,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LeaderboardEntry]:
        key = _build_leaderboard_key(custom_mode, mode, country)
        user_ids = await self._redis.zrevrange(key, offset, offset + limit - 1)

        if not user_ids:
            return []

        return await self._fetch_users_with_ranks(
            user_ids,
            mode,
            custom_mode,
            offset,
            country=country,
        )

    async def get_user_global_rank(
        self,
        user_id: int,
        mode: int,
        custom_mode: int,
    ) -> int:
        key = _build_leaderboard_key(custom_mode, mode)
        rank = await self._redis.zrevrank(key, str(user_id))
        if rank is None:
            return 0
        return rank + 1

    async def get_user_country_rank(
        self,
        user_id: int,
        mode: int,
        custom_mode: int,
        country: str,
    ) -> int:
        key = _build_leaderboard_key(custom_mode, mode, country)
        rank = await self._redis.zrevrank(key, str(user_id))
        if rank is None:
            return 0
        return rank + 1

    async def get_user_pp(
        self,
        user_id: int,
        mode: int,
        custom_mode: int,
    ) -> float | None:
        key = _build_leaderboard_key(custom_mode, mode)
        return await self._redis.zscore(key, str(user_id))

    async def _fetch_users_with_ranks(
        self,
        user_ids: list[str],
        mode: int,
        custom_mode: int,
        base_offset: int,
        country: str | None = None,
    ) -> list[LeaderboardEntry]:
        if not user_ids:
            return []

        table = get_stats_table(custom_mode)
        suffix = get_mode_suffix(mode)

        placeholders = ", ".join(f":id_{i}" for i in range(len(user_ids)))
        params = {f"id_{i}": int(uid) for i, uid in enumerate(user_ids)}

        query = f"""
            SELECT s.id, u.username, u.country, u.privileges,
                   s.pp_{suffix} as pp,
                   s.avg_accuracy_{suffix} as accuracy,
                   s.playcount_{suffix} as playcount,
                   s.total_score_{suffix} as total_score
            FROM {table} s
            INNER JOIN users u ON s.id = u.id
            WHERE s.id IN ({placeholders})
        """

        rows = await self._mysql.fetch_all(query, params)
        user_data = {row["id"]: row for row in rows}

        entries = []
        for i, uid_str in enumerate(user_ids):
            uid = int(uid_str)
            row = user_data.get(uid)
            if not row:
                continue

            country_rank = await self.get_user_country_rank(
                uid,
                mode,
                custom_mode,
                row["country"],
            )

            entries.append(
                LeaderboardEntry(
                    id=row["id"],
                    username=row["username"],
                    country=row["country"],
                    privileges=row["privileges"],
                    chosen_mode=LeaderboardModeStats(
                        pp=row["pp"] or 0,
                        accuracy=row["accuracy"] or 0.0,
                        playcount=row["playcount"] or 0,
                        level=_calculate_level(row["total_score"] or 0),
                    ),
                    global_rank=base_offset + i + 1,
                    country_rank=country_rank,
                ),
            )

        return entries

    async def list_oldest_firsts(
        self,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[FirstPlaceEntry]:
        query = """
            SELECT f.user_id as player_id, u.username, f.score_id, f.beatmap_md5,
                   b.song_name, f.pp, f.timestamp as achieved_at, f.mode
            FROM first_places f
            INNER JOIN users u ON f.user_id = u.id
            INNER JOIN beatmaps b ON f.beatmap_md5 = b.beatmap_md5
            WHERE f.mode = :mode
            AND f.relax = :relax
            AND u.privileges & 1 = 1
            ORDER BY f.timestamp ASC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"mode": mode, "relax": custom_mode, "limit": limit, "offset": offset},
        )

        return [FirstPlaceEntry(**row) for row in rows]

    async def get_total_ranked_users(
        self,
        mode: int,
        custom_mode: int,
    ) -> int:
        key = _build_leaderboard_key(custom_mode, mode)
        return await self._redis.zcard(key)

    async def get_country_total_ranked_users(
        self,
        mode: int,
        custom_mode: int,
        country: str,
    ) -> int:
        key = _build_leaderboard_key(custom_mode, mode, country)
        return await self._redis.zcard(key)
