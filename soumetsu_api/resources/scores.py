from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL

SCORE_TABLES = ["scores", "scores_relax", "scores_ap"]


class ScoreData(BaseModel):
    id: int
    beatmap_md5: str
    user_id: int
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
    time: str
    play_mode: int
    completed: int
    accuracy: float
    pp: float
    playtime: int


class ScoreWithBeatmap(ScoreData):
    beatmap_id: int
    song_name: str
    difficulty: float


class ScoresRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    def _get_table(self, playstyle: int) -> str:
        return SCORE_TABLES[playstyle]

    async def get_by_id(
        self,
        score_id: int,
        playstyle: int,
    ) -> ScoreData | None:
        table = self._get_table(playstyle)
        query = f"""
            SELECT id, beatmap_md5, userid as user_id, score, max_combo,
                   full_combo, mods, 300_count as count_300,
                   100_count as count_100, 50_count as count_50,
                   katus_count as count_katus, gekis_count as count_gekis,
                   misses_count as count_misses, time, play_mode,
                   completed, accuracy, pp, playtime
            FROM {table}
            WHERE id = :score_id
        """
        row = await self._mysql.fetch_one(query, {"score_id": score_id})
        if not row:
            return None

        return ScoreData(**row)

    async def get_user_best(
        self,
        user_id: int,
        mode: int,
        playstyle: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithBeatmap]:
        table = self._get_table(playstyle)
        diff_col = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ][mode]

        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as user_id, s.score,
                   s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime,
                   b.beatmap_id, b.song_name, b.{diff_col} as difficulty
            FROM {table} s
            INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
            WHERE s.userid = :user_id
            AND s.play_mode = :mode
            AND s.completed = 3
            ORDER BY s.pp DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"user_id": user_id, "mode": mode, "limit": limit, "offset": offset},
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def get_user_recent(
        self,
        user_id: int,
        mode: int,
        playstyle: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithBeatmap]:
        table = self._get_table(playstyle)
        diff_col = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ][mode]

        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as user_id, s.score,
                   s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime,
                   b.beatmap_id, b.song_name, b.{diff_col} as difficulty
            FROM {table} s
            INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
            WHERE s.userid = :user_id
            AND s.play_mode = :mode
            ORDER BY s.time DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"user_id": user_id, "mode": mode, "limit": limit, "offset": offset},
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def get_user_firsts(
        self,
        user_id: int,
        mode: int,
        playstyle: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithBeatmap]:
        diff_col = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ][mode]

        query = f"""
            SELECT f.score_id as id, f.beatmap_md5, f.user_id, f.score,
                   f.max_combo, f.full_combo, f.mods, f.300_count as count_300,
                   f.100_count as count_100, f.50_count as count_50,
                   f.ckatus_count as count_katus, f.cgekis_count as count_gekis,
                   f.miss_count as count_misses, f.timestamp as time, f.mode as play_mode,
                   f.completed, f.accuracy, f.pp, f.play_time as playtime,
                   b.beatmap_id, b.song_name, b.{diff_col} as difficulty
            FROM first_places f
            INNER JOIN beatmaps b ON f.beatmap_md5 = b.beatmap_md5
            WHERE f.user_id = :user_id
            AND f.mode = :mode
            AND f.relax = :relax
            ORDER BY f.timestamp DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {
                "user_id": user_id,
                "mode": mode,
                "relax": playstyle,
                "limit": limit,
                "offset": offset,
            },
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def get_user_pinned(
        self,
        user_id: int,
        mode: int,
        playstyle: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithBeatmap]:
        table = self._get_table(playstyle)
        diff_col = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ][mode]

        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as user_id, s.score,
                   s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime,
                   b.beatmap_id, b.song_name, b.{diff_col} as difficulty
            FROM user_pinned p
            INNER JOIN {table} s ON p.scoreid = s.id
            INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
            WHERE p.userid = :user_id
            AND s.play_mode = :mode
            ORDER BY p.pin_date DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"user_id": user_id, "mode": mode, "limit": limit, "offset": offset},
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def is_pinned(self, user_id: int, score_id: int) -> bool:
        count = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM user_pinned WHERE userid = :user_id AND scoreid = :score_id",
            {"user_id": user_id, "score_id": score_id},
        )
        return count > 0

    async def pin_score(self, user_id: int, score_id: int) -> None:
        import time

        await self._mysql.execute(
            """INSERT INTO user_pinned (userid, scoreid, pin_date)
               VALUES (:user_id, :score_id, :pin_date)
               ON DUPLICATE KEY UPDATE pin_date = :pin_date""",
            {
                "user_id": user_id,
                "score_id": score_id,
                "pin_date": str(int(time.time())),
            },
        )

    async def unpin_score(self, user_id: int, score_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM user_pinned WHERE userid = :user_id AND scoreid = :score_id",
            {"user_id": user_id, "score_id": score_id},
        )

    async def get_beatmap_scores(
        self,
        beatmap_md5: str,
        mode: int,
        playstyle: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreData]:
        table = self._get_table(playstyle)

        query = f"""
            SELECT id, beatmap_md5, userid as user_id, score, max_combo,
                   full_combo, mods, 300_count as count_300,
                   100_count as count_100, 50_count as count_50,
                   katus_count as count_katus, gekis_count as count_gekis,
                   misses_count as count_misses, time, play_mode,
                   completed, accuracy, pp, playtime
            FROM {table}
            WHERE beatmap_md5 = :beatmap_md5
            AND play_mode = :mode
            AND completed = 3
            ORDER BY pp DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {
                "beatmap_md5": beatmap_md5,
                "mode": mode,
                "limit": limit,
                "offset": offset,
            },
        )
        return [ScoreData(**row) for row in rows]
