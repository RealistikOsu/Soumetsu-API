from __future__ import annotations

import time as time_module

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.utilities import lazer

SCORE_TABLES = ["scores", "scores_relax", "scores_ap"]
DIFFICULTY_COLUMNS = [
    "difficulty_std",
    "difficulty_taiko",
    "difficulty_ctb",
    "difficulty_mania",
]


# osu!lazer scores count towards vanilla pp, so they show with the stable ones. Their ids are negated so they
# can't clash with a stable score's, and a negative id is how the rest of the API knows a score is lazer's.
def lazer_score_row_to_data(row: dict) -> dict:
    mods = row.pop("lazer_mods")
    counts = lazer.legacy_counts(row["play_mode"], row.pop("lazer_statistics"))
    return {
        **row,
        **counts,
        "id": -row["id"],
        "full_combo": counts["count_misses"] == 0,
        "mods": lazer.legacy_mod_bits(mods),
        "playback_rate": lazer.playback_rate(mods),
        "accuracy": row["accuracy"] * 100,
        "completed": 3,
        "playtime": 0,
    }


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

    def _get_table(self, custom_mode: int) -> str:
        return SCORE_TABLES[custom_mode]

    # Queries for one player's scores write "play_mode + 0" (and the same for completed) on purpose: it keeps
    # MySQL from intersecting those low-cardinality indexes with userid, which scanned far more rows than
    # walking the player's own scores and made profile lists take most of a second. Top plays order by
    # "pp + 0" for the same reason: with a small LIMIT, ordering by plain pp let MySQL walk the pp index
    # across every player's scores looking for this one's, which took several seconds for some profiles.

    async def find_by_id(
        self,
        score_id: int,
        custom_mode: int,
    ) -> ScoreData | None:
        if score_id < 0:
            return await self._find_lazer_by_id(-score_id)

        table = self._get_table(custom_mode)
        query = f"""
            SELECT id, beatmap_md5, userid as player_id, score, max_combo,
                   full_combo, mods, 300_count as count_300,
                   100_count as count_100, 50_count as count_50,
                   katus_count as count_katus, gekis_count as count_gekis,
                   misses_count as count_misses, time as submitted_at, play_mode,
                   completed, accuracy, pp, playtime, playback_rate
            FROM {table}
            WHERE id = :score_id
        """
        row = await self._mysql.fetch_one(query, {"score_id": score_id})
        if not row:
            return None

        return ScoreData(**row)

    async def _find_lazer_by_id(self, lazer_id: int) -> ScoreData | None:
        row = await self._mysql.fetch_one(
            """SELECT l.id, l.beatmap_md5, l.user_id AS player_id, l.total_score AS score,
                      l.max_combo, CAST(l.mods AS CHAR) AS lazer_mods,
                      CAST(l.statistics AS CHAR) AS lazer_statistics,
                      CAST(UNIX_TIMESTAMP(l.ended_at) AS SIGNED) AS submitted_at, l.ruleset_id AS play_mode,
                      l.accuracy, l.pp
               FROM lazer_scores l WHERE l.id = :id AND l.passed = 1""",
            {"id": lazer_id},
        )
        return ScoreData(**lazer_score_row_to_data(dict(row))) if row else None

    async def list_with_beatmap(
        self,
        score_ids: list[int],
        custom_mode: int,
    ) -> list[ScoreWithBeatmap]:
        table = self._get_table(custom_mode)
        placeholders = ", ".join(f":id{i}" for i in range(len(score_ids)))
        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as player_id, s.score,
                   s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time as submitted_at, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime, s.playback_rate,
                   b.beatmap_id, b.beatmapset_id, b.song_name, b.ranked,
                   CASE s.play_mode
                       WHEN 0 THEN b.difficulty_std
                       WHEN 1 THEN b.difficulty_taiko
                       WHEN 2 THEN b.difficulty_ctb
                       ELSE b.difficulty_mania
                   END as difficulty
            FROM {table} s
            INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
            WHERE s.id IN ({placeholders})
        """
        rows = await self._mysql.fetch_all(
            query,
            {f"id{i}": score_id for i, score_id in enumerate(score_ids)},
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def list_player_best(
        self,
        player_id: int,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithBeatmap]:
        if custom_mode == 0:
            with_lazer = await self._list_vanilla_best_with_lazer(
                player_id, mode, limit, offset
            )
            if with_lazer is not None:
                return with_lazer

        table = self._get_table(custom_mode)
        diff_col = DIFFICULTY_COLUMNS[mode]

        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as player_id, s.score,
                   s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time as submitted_at, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime, s.playback_rate,
                   b.beatmap_id, b.beatmapset_id, b.song_name,
                   b.{diff_col} as difficulty, b.ranked
            FROM {table} s
            INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
            WHERE s.userid = :player_id
            AND s.play_mode + 0 = :mode
            AND s.completed + 0 = 3
            AND b.ranked = 2
            ORDER BY s.pp + 0 DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"player_id": player_id, "mode": mode, "limit": limit, "offset": offset},
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    # The same set of plays the pp is worked out from (The-Pentagon, lazer and performance-service): each
    # beatmap's best play across stable and lazer. None when the lazer tables haven't been migrated.
    async def _list_vanilla_best_with_lazer(
        self, player_id: int, mode: int, limit: int, offset: int
    ) -> list[ScoreWithBeatmap] | None:
        try:
            picked = await self._mysql.fetch_all(
                """SELECT best.source, best.id FROM (
                       SELECT plays.source, plays.id, plays.pp,
                              ROW_NUMBER() OVER (PARTITION BY plays.beatmap_md5 ORDER BY plays.pp DESC) AS rn
                       FROM (
                           SELECT 'stable' AS source, s.id, s.beatmap_md5, s.pp FROM scores s
                           INNER JOIN beatmaps b ON b.beatmap_md5 = s.beatmap_md5
                           WHERE s.userid = :player_id AND s.play_mode + 0 = :mode
                             AND s.completed + 0 = 3 AND b.ranked IN (2, 3)
                           UNION ALL
                           SELECT 'lazer', l.id, l.beatmap_md5, l.pp FROM lazer_scores l
                           INNER JOIN beatmaps b ON b.beatmap_md5 = l.beatmap_md5
                           WHERE l.user_id = :player_id AND l.ruleset_id = :mode
                             AND l.passed = 1 AND l.pp > 0 AND b.ranked IN (2, 3)
                       ) plays
                   ) best
                   WHERE best.rn = 1
                   ORDER BY best.pp DESC
                   LIMIT :limit OFFSET :offset""",
                {
                    "player_id": player_id,
                    "mode": mode,
                    "limit": limit,
                    "offset": offset,
                },
            )
        except Exception as error:
            if "doesn't exist" in str(error):
                return None
            raise

        stable_ids = [row["id"] for row in picked if row["source"] == "stable"]
        lazer_ids = [row["id"] for row in picked if row["source"] == "lazer"]
        by_id = (
            {s.id: s for s in await self.list_with_beatmap(stable_ids, 0)}
            if stable_ids
            else {}
        )

        if lazer_ids:
            diff_col = DIFFICULTY_COLUMNS[mode]
            placeholders = ", ".join(f":id{i}" for i in range(len(lazer_ids)))
            rows = await self._mysql.fetch_all(
                f"""SELECT l.id, l.beatmap_md5, l.user_id AS player_id, l.total_score AS score,
                           l.max_combo, CAST(l.mods AS CHAR) AS lazer_mods,
                           CAST(l.statistics AS CHAR) AS lazer_statistics,
                           CAST(UNIX_TIMESTAMP(l.ended_at) AS SIGNED) AS submitted_at, l.ruleset_id AS play_mode,
                           l.accuracy, l.pp, b.beatmap_id, b.beatmapset_id, b.song_name,
                           b.{diff_col} AS difficulty, b.ranked
                    FROM lazer_scores l
                    INNER JOIN beatmaps b ON b.beatmap_md5 = l.beatmap_md5
                    WHERE l.id IN ({placeholders})""",
                {f"id{i}": lazer_id for i, lazer_id in enumerate(lazer_ids)},
            )
            for row in rows:
                score = ScoreWithBeatmap(**lazer_score_row_to_data(dict(row)))
                by_id[score.id] = score

        return [
            by_id[-row["id"] if row["source"] == "lazer" else row["id"]]
            for row in picked
        ]

    async def list_player_recent(
        self,
        player_id: int,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
        exclude_failed: bool = False,
    ) -> list[ScoreWithBeatmap]:
        table = self._get_table(custom_mode)
        # IDs follow submission order, and sorting by them walks the index instead of sorting every one of
        # the player's scores by time.
        passed_only = "AND s.completed + 0 >= 1" if exclude_failed else ""
        diff_col = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ][mode]

        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as player_id, s.score,
                   s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time as submitted_at, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime, s.playback_rate,
                   b.beatmap_id, b.beatmapset_id, b.song_name,
                   b.{diff_col} as difficulty, b.ranked
            FROM {table} s
            INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
            WHERE s.userid = :player_id
            AND s.play_mode + 0 = :mode
            {passed_only}
            ORDER BY s.id DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"player_id": player_id, "mode": mode, "limit": limit, "offset": offset},
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
        table = self._get_table(custom_mode)
        diff_col = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ][mode]

        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as player_id, s.score,
                   s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time as submitted_at, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime, s.playback_rate,
                   b.beatmap_id, b.beatmapset_id, b.song_name,
                   b.{diff_col} as difficulty, b.ranked
            FROM first_places f
            INNER JOIN {table} s ON f.score_id = s.id
            INNER JOIN beatmaps b ON f.beatmap_md5 = b.beatmap_md5
            WHERE f.user_id = :player_id
            AND f.mode = :mode
            AND f.relax = :relax
            ORDER BY f.timestamp DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {
                "player_id": player_id,
                "mode": mode,
                "relax": custom_mode,
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
        table = self._get_table(custom_mode)
        diff_col = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ][mode]

        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as player_id, s.score,
                   s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time as submitted_at, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime, s.playback_rate,
                   b.beatmap_id, b.beatmapset_id, b.song_name,
                   b.{diff_col} as difficulty, b.ranked
            FROM user_pinned p
            INNER JOIN {table} s ON p.scoreid = s.id
            INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
            WHERE p.userid = :player_id
            AND s.play_mode = :mode
            ORDER BY p.pin_date DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"player_id": player_id, "mode": mode, "limit": limit, "offset": offset},
        )
        return [ScoreWithBeatmap(**row) for row in rows]

    async def is_pinned(self, player_id: int, score_id: int) -> bool:
        count = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM user_pinned WHERE userid = :player_id AND scoreid = :score_id",
            {"player_id": player_id, "score_id": score_id},
        )
        return count > 0

    async def pin_score(self, player_id: int, score_id: int) -> None:
        pinned_at = str(int(time_module.time()))
        await self._mysql.execute(
            """INSERT INTO user_pinned (userid, scoreid, pin_date)
               VALUES (:player_id, :score_id, :pinned_at)
               ON DUPLICATE KEY UPDATE pin_date = :pinned_at""",
            {
                "player_id": player_id,
                "score_id": score_id,
                "pinned_at": pinned_at,
            },
        )

    async def unpin_score(self, player_id: int, score_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM user_pinned WHERE userid = :player_id AND scoreid = :score_id",
            {"player_id": player_id, "score_id": score_id},
        )

    async def list_top_plays(
        self,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreTopPlay]:
        table = self._get_table(custom_mode)
        diff_col = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ][mode]

        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as player_id, s.score,
                   s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time as submitted_at, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime, s.playback_rate,
                   b.beatmap_id, b.beatmapset_id, b.song_name,
                   b.{diff_col} as difficulty, b.ranked,
                   u.username
            FROM {table} s
            INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
            INNER JOIN users u ON s.userid = u.id
            WHERE s.play_mode = :mode
            AND s.completed = 3
            AND s.pp > 0
            AND b.ranked = 2
            AND u.privileges & 1 > 0
            ORDER BY s.pp DESC
            LIMIT :limit OFFSET :offset
        """
        rows = await self._mysql.fetch_all(
            query,
            {"mode": mode, "limit": limit, "offset": offset},
        )
        return [ScoreTopPlay(**row) for row in rows]

    async def list_top_plays_all_modes(self) -> list[ScoreTopPlayWithMode]:
        # Valid combinations:
        # custom_mode 0 (vanilla): modes 0,1,2,3 (std, taiko, ctb, mania)
        # custom_mode 1 (relax): modes 0,1,2 (std, taiko, ctb)
        # custom_mode 2 (autopilot): mode 0 only (std)
        diff_cols = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ]

        mode_queries = []
        for custom_mode, table in enumerate(SCORE_TABLES):
            if custom_mode == 0:
                modes = [0, 1, 2, 3]
            elif custom_mode == 1:
                modes = [0, 1, 2]
            else:
                modes = [0]

            for mode in modes:
                diff_col = diff_cols[mode]
                mode_queries.append(
                    f"""
                    (SELECT s.id, s.beatmap_md5, s.userid as player_id, s.score,
                            s.max_combo, s.full_combo, s.mods, s.300_count as count_300,
                            s.100_count as count_100, s.50_count as count_50,
                            s.katus_count as count_katus, s.gekis_count as count_gekis,
                            s.misses_count as count_misses, s.time as submitted_at, s.play_mode,
                            s.completed, s.accuracy, s.pp, s.playtime, s.playback_rate,
                            b.beatmap_id, b.beatmapset_id, b.song_name,
                            b.{diff_col} as difficulty, b.ranked,
                            u.username, {custom_mode} as custom_mode
                     FROM {table} s
                     INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
                     INNER JOIN users u ON s.userid = u.id
                     WHERE s.play_mode = {mode} AND s.completed = 3 AND s.pp > 0
                       AND b.ranked = 2 AND u.privileges & 1 > 0
                     ORDER BY s.pp DESC LIMIT 1)
                """,
                )

        query = " UNION ALL ".join(mode_queries) + " ORDER BY pp DESC"
        rows = await self._mysql.fetch_all(query, {})
        return [ScoreTopPlayWithMode(**row) for row in rows]

    async def list_beatmap_scores(
        self,
        beatmap_md5: str,
        mode: int,
        custom_mode: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScoreWithPlayer]:
        table = self._get_table(custom_mode)

        query = f"""
            SELECT s.id, s.beatmap_md5, s.userid as player_id, s.score, s.max_combo,
                   s.full_combo, s.mods, s.300_count as count_300,
                   s.100_count as count_100, s.50_count as count_50,
                   s.katus_count as count_katus, s.gekis_count as count_gekis,
                   s.misses_count as count_misses, s.time as submitted_at, s.play_mode,
                   s.completed, s.accuracy, s.pp, s.playtime, s.playback_rate,
                   u.id as player_db_id, u.username, u.country
            FROM {table} s
            INNER JOIN users u ON s.userid = u.id
            WHERE s.beatmap_md5 = :beatmap_md5
            AND s.play_mode = :mode
            AND s.completed = 3
            AND u.privileges & 1 > 0
            ORDER BY s.pp DESC
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
