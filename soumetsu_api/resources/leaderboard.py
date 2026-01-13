from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL

STATS_TABLES = ["users_stats", "rx_stats", "ap_stats"]
MODE_SUFFIXES = ["std", "taiko", "ctb", "mania"]


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
    rank: int


class FirstPlaceEntry(BaseModel):
    player_id: int
    username: str
    score_id: int
    beatmap_md5: str
    song_name: str
    pp: float
    achieved_at: int
    mode: int


class LeaderboardRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    def _get_table(self, playstyle: int) -> str:
        return STATS_TABLES[playstyle]

    def _get_mode_suffix(self, mode: int) -> str:
        return MODE_SUFFIXES[mode]

    def _calculate_level(self, total_score: int) -> float:
        if total_score <= 0:
            return 1.0

        level = 1
        score_req = 0

        while score_req <= total_score:
            level += 1
            if level <= 100:
                score_req += 5000 // 3 * (4 * (level ** 3) - 3 * (level ** 2) - level) + \
                            1250 * (1.8 ** (level - 60)) // 3
            else:
                score_req += 26931190829 + 100000000000 * (level - 100)

            if level > 120:
                break

        progress = 0.0
        if level > 1:
            prev_req = 0
            for l in range(2, level):
                if l <= 100:
                    prev_req += 5000 // 3 * (4 * (l ** 3) - 3 * (l ** 2) - l) + \
                               1250 * (1.8 ** (l - 60)) // 3
                else:
                    prev_req += 26931190829 + 100000000000 * (l - 100)

            if score_req > prev_req:
                progress = (total_score - prev_req) / (score_req - prev_req)

        return float(level - 1) + progress

    async def get_global(
        self,
        mode: int,
        playstyle: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LeaderboardEntry]:
        table = self._get_table(playstyle)
        suffix = self._get_mode_suffix(mode)

        query = f"""
            SELECT s.id, u.username, u.country, u.privileges,
                   s.pp_{suffix} as pp,
                   s.avg_accuracy_{suffix} as accuracy,
                   s.playcount_{suffix} as playcount,
                   s.total_score_{suffix} as total_score
            FROM {table} s
            INNER JOIN users u ON s.id = u.id
            WHERE u.privileges & 1 = 1
            AND s.pp_{suffix} > 0
            ORDER BY s.pp_{suffix} DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"limit": limit, "offset": offset},
        )

        return [
            LeaderboardEntry(
                id=row["id"],
                username=row["username"],
                country=row["country"],
                privileges=row["privileges"],
                chosen_mode=LeaderboardModeStats(
                    pp=row["pp"],
                    accuracy=row["accuracy"],
                    playcount=row["playcount"],
                    level=self._calculate_level(row["total_score"] or 0),
                ),
                rank=offset + i + 1,
            )
            for i, row in enumerate(rows)
        ]

    async def get_country(
        self,
        country: str,
        mode: int,
        playstyle: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LeaderboardEntry]:
        table = self._get_table(playstyle)
        suffix = self._get_mode_suffix(mode)

        query = f"""
            SELECT s.id, u.username, u.country, u.privileges,
                   s.pp_{suffix} as pp,
                   s.avg_accuracy_{suffix} as accuracy,
                   s.playcount_{suffix} as playcount,
                   s.total_score_{suffix} as total_score
            FROM {table} s
            INNER JOIN users u ON s.id = u.id
            WHERE u.privileges & 1 = 1
            AND u.country = :country
            AND s.pp_{suffix} > 0
            ORDER BY s.pp_{suffix} DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"country": country.upper(), "limit": limit, "offset": offset},
        )

        return [
            LeaderboardEntry(
                id=row["id"],
                username=row["username"],
                country=row["country"],
                privileges=row["privileges"],
                chosen_mode=LeaderboardModeStats(
                    pp=row["pp"],
                    accuracy=row["accuracy"],
                    playcount=row["playcount"],
                    level=self._calculate_level(row["total_score"] or 0),
                ),
                rank=offset + i + 1,
            )
            for i, row in enumerate(rows)
        ]

    async def get_rank_for_pp(
        self,
        pp: int,
        mode: int,
        playstyle: int,
    ) -> int:
        table = self._get_table(playstyle)
        suffix = self._get_mode_suffix(mode)

        query = f"""
            SELECT COUNT(*) + 1 as `rank`
            FROM {table} s
            INNER JOIN users u ON s.id = u.id
            WHERE u.privileges & 1 = 1
            AND s.pp_{suffix} > :pp
        """
        result = await self._mysql.fetch_val(query, {"pp": pp})
        return result or 1

    async def list_oldest_firsts(
        self,
        mode: int,
        playstyle: int,
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
            {"mode": mode, "relax": playstyle, "limit": limit, "offset": offset},
        )

        return [FirstPlaceEntry(**row) for row in rows]
