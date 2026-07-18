from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.constants import combined_mode

# Columns pulled from the clean `scores` table, aliased to the model field
# names the API layer already expects.
_SCORE_COLUMNS = """
    s.id, s.beatmap_md5, s.user_id as player_id, s.score, s.max_combo,
    s.full_combo, s.mods, s.count_300, s.count_100, s.count_50,
    s.count_katu as count_katus, s.count_geki as count_gekis,
    s.count_miss as count_misses,
    UNIX_TIMESTAMP(s.submitted_at) as submitted_at, s.mode as play_mode,
    s.status as completed, s.accuracy, s.pp, s.playtime, s.playback_rate
"""

# Split-beatmap columns + join clause (composed song_name; per-mode stars).
_BEATMAP_COLUMNS = """
    b.id as beatmap_id, b.set_id as beatmapset_id,
    CONCAT(bs.artist, ' - ', bs.title, ' [', b.version, ']') as song_name,
    bd.stars as difficulty, b.status as ranked
"""

_BEATMAP_JOIN = """
    INNER JOIN beatmaps b ON s.beatmap_md5 = b.md5
    INNER JOIN beatmapsets bs ON b.set_id = bs.id
    LEFT JOIN beatmap_difficulty bd ON bd.beatmap_id = b.id AND bd.mode = :diff_mode
"""


def _decompose_mode(cmode: int) -> tuple[int, int]:
    """Clean-schema combined mode 0-7 -> (mode, custom_mode)."""
    if cmode == 7:
        return 0, 2
    if cmode >= 4:
        return cmode - 4, 1
    return cmode, 0


class ScoreData(BaseModel):
    id: int
    beatmap_md5: str
    player_id: int
    score: int
    max_combo: int
    full_combo: bool
    mods: int
    count_300: int
    count_100: int
    count_50: int
    count_katus: int
    count_gekis: int
    count_misses: int
    submitted_at: int
    play_mode: int
    completed: int
    accuracy: float
    pp: float
    playtime: int
    playback_rate: float


class ScoreWithBeatmap(ScoreData):
    beatmap_id: int
    beatmapset_id: int
    song_name: str
    difficulty: float
    ranked: int


class ScorePlayer(BaseModel):
    player_id: int
    username: str
    country: str


class ScoreWithPlayer(ScoreData):
    player: ScorePlayer


class ScoreTopPlay(ScoreWithBeatmap):
    username: str


class ScoreTopPlayWithMode(ScoreTopPlay):
    custom_mode: int = 0


class ScoresRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def find_by_id(
        self,
        score_id: int,
        custom_mode: int,
    ) -> ScoreData | None:
        query = f"""
            SELECT {_SCORE_COLUMNS}
            FROM scores s
            WHERE s.id = :score_id
        """
        row = await self._mysql.fetch_one(query, {"score_id": score_id})
        if not row:
            return None

        return ScoreData(**row)

    async def list_player_best(
        self,
        player_id: int,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithBeatmap]:
        cmode = combined_mode(mode, custom_mode)
        query = f"""
            SELECT {_SCORE_COLUMNS}, {_BEATMAP_COLUMNS}
            FROM scores s
            {_BEATMAP_JOIN}
            WHERE s.user_id = :player_id
            AND s.mode = :cmode
            AND s.status = 3
            AND b.status = 2
            ORDER BY s.pp DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {
                "player_id": player_id,
                "cmode": cmode,
                "diff_mode": mode,
                "limit": limit,
                "offset": offset,
            },
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def list_player_recent(
        self,
        player_id: int,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithBeatmap]:
        cmode = combined_mode(mode, custom_mode)
        query = f"""
            SELECT {_SCORE_COLUMNS}, {_BEATMAP_COLUMNS}
            FROM scores s
            {_BEATMAP_JOIN}
            WHERE s.user_id = :player_id
            AND s.mode = :cmode
            ORDER BY s.submitted_at DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {
                "player_id": player_id,
                "cmode": cmode,
                "diff_mode": mode,
                "limit": limit,
                "offset": offset,
            },
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def list_player_firsts(
        self,
        player_id: int,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithBeatmap]:
        cmode = combined_mode(mode, custom_mode)
        query = f"""
            SELECT {_SCORE_COLUMNS}, {_BEATMAP_COLUMNS}
            FROM first_places f
            INNER JOIN scores s ON f.score_id = s.id
            {_BEATMAP_JOIN}
            WHERE f.user_id = :player_id
            AND f.mode = :cmode
            ORDER BY s.submitted_at DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {
                "player_id": player_id,
                "cmode": cmode,
                "diff_mode": mode,
                "limit": limit,
                "offset": offset,
            },
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def list_player_pinned(
        self,
        player_id: int,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithBeatmap]:
        cmode = combined_mode(mode, custom_mode)
        query = f"""
            SELECT {_SCORE_COLUMNS}, {_BEATMAP_COLUMNS}
            FROM user_pinned p
            INNER JOIN scores s ON p.score_id = s.id
            {_BEATMAP_JOIN}
            WHERE p.user_id = :player_id
            AND s.mode = :cmode
            ORDER BY p.pinned_at DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {
                "player_id": player_id,
                "cmode": cmode,
                "diff_mode": mode,
                "limit": limit,
                "offset": offset,
            },
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def is_pinned(self, player_id: int, score_id: int) -> bool:
        count = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM user_pinned WHERE user_id = :player_id AND score_id = :score_id",
            {"player_id": player_id, "score_id": score_id},
        )
        return count > 0

    async def pin_score(self, player_id: int, score_id: int) -> None:
        await self._mysql.execute(
            """INSERT INTO user_pinned (user_id, score_id)
               VALUES (:player_id, :score_id)
               ON DUPLICATE KEY UPDATE pinned_at = CURRENT_TIMESTAMP""",
            {"player_id": player_id, "score_id": score_id},
        )

    async def unpin_score(self, player_id: int, score_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM user_pinned WHERE user_id = :player_id AND score_id = :score_id",
            {"player_id": player_id, "score_id": score_id},
        )

    async def list_top_plays(
        self,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreTopPlay]:
        cmode = combined_mode(mode, custom_mode)
        query = f"""
            SELECT {_SCORE_COLUMNS}, {_BEATMAP_COLUMNS}, u.username
            FROM scores s
            {_BEATMAP_JOIN}
            INNER JOIN users u ON s.user_id = u.id
            WHERE s.mode = :cmode
            AND s.status = 3
            AND s.pp > 0
            AND b.status = 2
            AND u.public = 1
            ORDER BY s.pp DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"cmode": cmode, "diff_mode": mode, "limit": limit, "offset": offset},
        )
        return [ScoreTopPlay(**row) for row in rows]

    async def list_top_plays_all_modes(self) -> list[ScoreTopPlayWithMode]:
        # One top play per combined mode 0-7.
        mode_queries = []
        params: dict[str, int] = {}
        for cmode in range(8):
            vmode, custom_mode = _decompose_mode(cmode)
            params[f"diff_mode_{cmode}"] = vmode
            mode_queries.append(
                f"""
                (SELECT {_SCORE_COLUMNS},
                        b.id as beatmap_id, b.set_id as beatmapset_id,
                        CONCAT(bs.artist, ' - ', bs.title, ' [', b.version, ']') as song_name,
                        bd.stars as difficulty, b.status as ranked,
                        u.username, {custom_mode} as custom_mode
                 FROM scores s
                 INNER JOIN beatmaps b ON s.beatmap_md5 = b.md5
                 INNER JOIN beatmapsets bs ON b.set_id = bs.id
                 LEFT JOIN beatmap_difficulty bd ON bd.beatmap_id = b.id AND bd.mode = :diff_mode_{cmode}
                 INNER JOIN users u ON s.user_id = u.id
                 WHERE s.mode = {cmode} AND s.status = 3 AND s.pp > 0
                   AND b.status = 2 AND u.public = 1
                 ORDER BY s.pp DESC LIMIT 1)
            """,
            )

        query = " UNION ALL ".join(mode_queries) + " ORDER BY pp DESC"
        rows = await self._mysql.fetch_all(query, params)
        return [ScoreTopPlayWithMode(**row) for row in rows]

    async def list_beatmap_scores(
        self,
        beatmap_md5: str,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithPlayer]:
        cmode = combined_mode(mode, custom_mode)
        query = f"""
            SELECT {_SCORE_COLUMNS},
                   u.id as player_db_id, u.username, u.country
            FROM scores s
            INNER JOIN users u ON s.user_id = u.id
            WHERE s.beatmap_md5 = :beatmap_md5
            AND s.mode = :cmode
            AND s.status = 3
            ORDER BY s.pp DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {
                "beatmap_md5": beatmap_md5,
                "cmode": cmode,
                "limit": limit,
                "offset": offset,
            },
        )
        return [
            ScoreWithPlayer(
                id=row["id"],
                beatmap_md5=row["beatmap_md5"],
                player_id=row["player_id"],
                score=row["score"],
                max_combo=row["max_combo"],
                full_combo=row["full_combo"],
                mods=row["mods"],
                count_300=row["count_300"],
                count_100=row["count_100"],
                count_50=row["count_50"],
                count_katus=row["count_katus"],
                count_gekis=row["count_gekis"],
                count_misses=row["count_misses"],
                submitted_at=row["submitted_at"],
                play_mode=row["play_mode"],
                completed=row["completed"],
                accuracy=row["accuracy"],
                pp=row["pp"],
                playtime=row["playtime"],
                playback_rate=row["playback_rate"],
                player=ScorePlayer(
                    player_id=row["player_db_id"],
                    username=row["username"],
                    country=row["country"],
                ),
            )
            for row in rows
        ]
