"""Unit tests for osu!lazer scores in the scores repository."""

from __future__ import annotations

import pytest

from soumetsu_api.constants import STATS_TABLES
from soumetsu_api.constants import CustomMode
from soumetsu_api.constants import is_valid_custom_mode
from soumetsu_api.resources import scores
from soumetsu_api.resources.leaderboard import _build_leaderboard_key
from soumetsu_api.services import scores as scores_service
from soumetsu_api.utilities.grades import stable_grade
from soumetsu_api.utilities.mods import OsuMods
from tests.conftest import MockContext
from tests.conftest import MockMySQLAdapter

LAZER_MODES = [
    (CustomMode.LAZER, 0),
    (CustomMode.LAZER_RELAX, 1),
    (CustomMode.LAZER_AUTOPILOT, 2),
]

LAZER_ROW = {
    "id": 12,
    "beatmap_md5": "b" * 32,
    "player_id": 5,
    "score": 900_000,
    "max_combo": 300,
    "lazer_mods": '[{"acronym": "DT", "settings": {"speed_change": 1.3}}]',
    "lazer_statistics": '{"great": 250, "ok": 10, "meh": 2, "miss": 1}',
    "submitted_at": 1_700_000_000,
    "play_mode": 0,
    "accuracy": 0.9875,
    "pp": 321.5,
    "passed": 1,
    "has_replay": 1,
}


def test_lazer_row_becomes_score_data() -> None:
    data = scores.lazer_score_row_to_data(dict(LAZER_ROW))

    score = scores.ScoreData(**data)

    assert score.id == 12
    assert score.accuracy == pytest.approx(98.75)
    assert score.count_300 == 250
    assert score.count_misses == 1
    assert not score.full_combo
    assert score.mods == 64
    assert score.playback_rate == 1.3
    assert score.completed == 3
    assert score.has_replay is True


def test_failed_lazer_row_is_not_completed() -> None:
    data = scores.lazer_score_row_to_data({**LAZER_ROW, "passed": 0})

    assert data["completed"] == 0


class RecordingMySQL(MockMySQLAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.values: list[dict] = []

    async def fetch_one(self, query, values=None):
        self.values.append(values)
        return await super().fetch_one(query, values)

    async def fetch_all(self, query, values=None):
        self.values.append(values)
        return await super().fetch_all(query, values)


class TestRepository:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("custom_mode", "variant"), LAZER_MODES)
    async def test_find_by_id_reads_lazer_scores(
        self, custom_mode: CustomMode, variant: int
    ) -> None:
        mysql = RecordingMySQL()
        mysql.set_result("FROM lazer_scores", dict(LAZER_ROW))

        score = await scores.ScoresRepository(mysql).find_by_id(12, custom_mode)

        assert score is not None
        assert score.id == 12
        assert mysql.values == [{"id": 12, "variant": variant}]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("custom_mode", "variant"), LAZER_MODES)
    async def test_lazer_best_plays_carry_their_beatmap(
        self, custom_mode: CustomMode, variant: int
    ) -> None:
        row = {
            **LAZER_ROW,
            "beatmap_id": 7,
            "beatmapset_id": 70,
            "song_name": "Artist - Title [Insane]",
            "difficulty": 5.4,
            "ranked": 2,
        }
        mysql = RecordingMySQL()
        mysql.set_result("NOT EXISTS", [row])

        best = await scores.ScoresRepository(mysql).list_player_best(5, 0, custom_mode)

        assert [(s.id, s.beatmap_id, s.pp) for s in best] == [(12, 7, 321.5)]
        assert mysql.values[0]["variant"] == variant

    @pytest.mark.asyncio
    @pytest.mark.parametrize("custom_mode", [m for m, _ in LAZER_MODES])
    @pytest.mark.parametrize("method", ["list_player_firsts", "list_player_pinned"])
    async def test_lazer_has_no_firsts_or_pins(
        self, mock_mysql: MockMySQLAdapter, method: str, custom_mode: CustomMode
    ) -> None:
        repository = scores.ScoresRepository(mock_mysql)

        assert await getattr(repository, method)(5, 0, custom_mode) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("custom_mode", [m for m, _ in LAZER_MODES])
async def test_lazer_scores_cannot_be_pinned(
    mock_context: MockContext, custom_mode: CustomMode
) -> None:
    result = await scores_service.pin_score(mock_context, 5, 12, custom_mode)

    assert result == scores_service.ScoreError.INVALID_CUSTOM_MODE


@pytest.mark.parametrize(
    ("custom_mode", "prefix"),
    [
        (CustomMode.LAZER, "ripple:leaderboard_lazer"),
        (CustomMode.LAZER_RELAX, "ripple:leaderboard_lazer_relax"),
        (CustomMode.LAZER_AUTOPILOT, "ripple:leaderboard_lazer_ap"),
    ],
)
def test_lazer_leaderboard_keys(custom_mode: CustomMode, prefix: str) -> None:
    assert _build_leaderboard_key(custom_mode, 3) == f"{prefix}:mania"
    assert _build_leaderboard_key(custom_mode, 0, "GB") == f"{prefix}:std:gb"


def test_lazer_variants_have_their_own_stats_tables() -> None:
    assert [STATS_TABLES[m] for m, _ in LAZER_MODES] == [
        "lazer_stats",
        "lazer_rx_stats",
        "lazer_ap_stats",
    ]


def test_custom_mode_range() -> None:
    assert is_valid_custom_mode(5)
    assert not is_valid_custom_mode(6)


DETAIL_ROW = {
    **LAZER_ROW,
    "variant": 1,
    "rank": "S",
    "has_replay": 1,
    "ranked_mods": 1,
    "beatmap_id": 7,
    "beatmap_set_id": 70,
    "song_name": "Artist - Title [Insane]",
    "creator": "Mapper",
    "stars": 5.4,
    "beatmap_mode": 0,
    "beatmap_ranked": 2,
    "username": "Player",
    "country": "GB",
    "privileges": 7,
    "latest_activity": 1_700_000_500,
}
DETAIL_QUERY = "mu.username AS creator"
RANK_QUERY = "AS better_own"


def test_lazer_detail_row_keeps_stored_json() -> None:
    detail = scores.lazer_detail_row_to_data(dict(DETAIL_ROW))

    assert detail.statistics == {"great": 250, "ok": 10, "meh": 2, "miss": 1}
    assert detail.mods == [{"acronym": "DT", "settings": {"speed_change": 1.3}}]
    assert detail.accuracy == pytest.approx(98.75)
    assert detail.has_replay
    assert detail.beatmap is not None
    assert detail.beatmap.beatmapset_id == 70
    assert detail.player.last_active == 1_700_000_500


def test_lazer_detail_row_without_beatmap() -> None:
    detail = scores.lazer_detail_row_to_data({**DETAIL_ROW, "beatmap_set_id": None})

    assert detail.beatmap is None


class TestLazerDetail:
    @pytest.mark.asyncio
    async def test_hides_restricted_players(
        self, mock_mysql: MockMySQLAdapter, mock_context: MockContext
    ) -> None:
        mock_mysql.set_result(DETAIL_QUERY, {**DETAIL_ROW, "privileges": 2})

        result = await scores_service.get_lazer_score(mock_context, 12)

        assert result == scores_service.ScoreError.SCORE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_unknown_score_is_not_found(self, mock_context: MockContext) -> None:
        result = await scores_service.get_lazer_score(mock_context, 12)

        assert result == scores_service.ScoreError.SCORE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_rank_is_one_past_the_players_ahead(
        self, mock_mysql: MockMySQLAdapter, mock_context: MockContext
    ) -> None:
        mock_mysql.set_result(DETAIL_QUERY, dict(DETAIL_ROW))
        mock_mysql.set_result(RANK_QUERY, {"better_own": 0, "ahead": 4})

        result = await scores_service.get_lazer_score(mock_context, 12)

        assert not isinstance(result, scores_service.ScoreError)
        assert result.global_rank == 5

    @pytest.mark.asyncio
    async def test_no_rank_when_the_player_has_a_better_score(
        self, mock_mysql: MockMySQLAdapter, mock_context: MockContext
    ) -> None:
        mock_mysql.set_result(DETAIL_QUERY, dict(DETAIL_ROW))
        mock_mysql.set_result(RANK_QUERY, {"better_own": 1, "ahead": 4})

        result = await scores_service.get_lazer_score(mock_context, 12)

        assert not isinstance(result, scores_service.ScoreError)
        assert result.global_rank is None


STABLE_ROW = {
    "id": 30,
    "beatmap_md5": "c" * 32,
    "player_id": 5,
    "score": 1_200_000,
    "max_combo": 400,
    "mods": int(OsuMods.HD | OsuMods.DT),
    "count_300": 480,
    "count_100": 15,
    "count_50": 3,
    "count_katus": 8,
    "count_gekis": 90,
    "count_misses": 2,
    "submitted_at": 1_700_000_000,
    "play_mode": 0,
    "completed": 3,
    "accuracy": 98.5,
    "pp": 410.25,
    "playback_rate": 1.5,
    "beatmap_id": 7,
    "beatmap_set_id": 70,
    "song_name": "Artist - Title [Insane]",
    "creator": "Mapper",
    "stars": 5.4,
    "beatmap_mode": 0,
    "beatmap_ranked": 2,
    "username": "Player",
    "country": "GB",
    "privileges": 7,
    "latest_activity": 1_700_000_500,
}
STABLE_QUERY = "mu.username AS creator"
STABLE_RANK_QUERY = "AS ahead"


def test_stable_detail_row_matches_the_lazer_shape() -> None:
    detail = scores.stable_detail_row_to_data(dict(STABLE_ROW), 0)

    assert detail.variant == 0
    assert detail.accuracy == pytest.approx(98.5)
    assert detail.passed
    assert detail.has_replay
    assert detail.ranked_mods
    assert detail.statistics == {"great": 480, "ok": 15, "meh": 3, "miss": 2}
    assert detail.beatmap is not None
    assert detail.beatmap.beatmapset_id == 70
    assert detail.player.last_active == 1_700_000_500
    assert [m["acronym"] for m in detail.mods] == ["CL", "HD", "DT"]
    assert detail.mods[2]["settings"] == {"speed_change": 1.5}
    assert detail.mods[1]["settings"] is None


def test_stable_detail_has_no_speed_settings_at_normal_rate() -> None:
    detail = scores.stable_detail_row_to_data({**STABLE_ROW, "playback_rate": 1.0}, 0)

    assert detail.mods[2] == {"acronym": "DT", "settings": None}


def test_stable_detail_replay_only_for_best_scores() -> None:
    detail = scores.stable_detail_row_to_data({**STABLE_ROW, "completed": 2}, 0)

    assert detail.passed
    assert not detail.has_replay


def test_stable_detail_failed_score() -> None:
    detail = scores.stable_detail_row_to_data({**STABLE_ROW, "completed": 0}, 1)

    assert not detail.passed
    assert detail.rank == "F"
    assert detail.variant == 1


@pytest.mark.parametrize(
    ("play_mode", "statistics"),
    [
        (1, {"great": 480, "ok": 15, "miss": 2}),
        (
            2,
            {
                "great": 480,
                "large_tick_hit": 15,
                "small_tick_hit": 3,
                "small_tick_miss": 8,
                "miss": 2,
            },
        ),
        (
            3,
            {"perfect": 90, "great": 480, "good": 8, "ok": 15, "meh": 3, "miss": 2},
        ),
    ],
)
def test_stable_statistics_per_mode(play_mode: int, statistics: dict) -> None:
    assert (
        scores.stable_statistics({**STABLE_ROW, "play_mode": play_mode}) == statistics
    )


@pytest.mark.parametrize(
    ("play_mode", "mods", "counts", "completed", "grade"),
    [
        (0, 0, (100, 0, 0, 0, 0, 0), 3, "X"),
        (0, int(OsuMods.HD), (100, 0, 0, 0, 0, 0), 3, "XH"),
        (0, int(OsuMods.FL), (95, 5, 0, 0, 0, 0), 3, "SH"),
        (0, 0, (95, 5, 0, 0, 0, 0), 3, "S"),
        (0, 0, (95, 0, 5, 0, 0, 0), 3, "A"),
        (0, 0, (95, 4, 0, 0, 0, 1), 3, "A"),
        (0, 0, (85, 15, 0, 0, 0, 0), 3, "A"),
        (0, 0, (75, 25, 0, 0, 0, 0), 3, "B"),
        (0, 0, (85, 10, 0, 0, 0, 5), 3, "B"),
        (0, 0, (65, 35, 0, 0, 0, 0), 3, "C"),
        (0, 0, (50, 50, 0, 0, 0, 0), 3, "D"),
        (0, 0, (0, 0, 0, 0, 0, 0), 3, "D"),
        (0, 0, (100, 0, 0, 0, 0, 0), 0, "F"),
        (1, 0, (100, 0, 0, 0, 0, 0), 1, "X"),
        (1, 0, (95, 5, 0, 0, 0, 0), 1, "S"),
        (2, 0, (100, 0, 0, 0, 0, 0), 3, "X"),
        (2, int(OsuMods.HD), (990, 0, 0, 0, 0, 5), 3, "SH"),
        (2, 0, (950, 0, 0, 0, 0, 50), 3, "A"),
        (2, 0, (910, 0, 0, 0, 0, 90), 3, "B"),
        (2, 0, (860, 0, 0, 0, 0, 140), 3, "C"),
        (2, 0, (500, 0, 0, 0, 0, 500), 3, "D"),
        (3, 0, (100, 0, 0, 0, 0, 0), 3, "X"),
        (3, int(OsuMods.FL), (100, 0, 0, 0, 100, 0), 3, "XH"),
        (3, 0, (96, 4, 0, 0, 0, 0), 3, "S"),
        (3, 0, (90, 10, 0, 0, 0, 0), 3, "A"),
        (3, 0, (70, 30, 0, 0, 0, 0), 3, "C"),
        (3, 0, (50, 50, 0, 0, 0, 0), 3, "D"),
    ],
)
def test_stable_grade(
    play_mode: int,
    mods: int,
    counts: tuple[int, int, int, int, int, int],
    completed: int,
    grade: str,
) -> None:
    # counts: 300, 100, 50, katus, gekis, misses
    c300, c100, c50, katus, gekis, misses = counts

    assert (
        stable_grade(play_mode, mods, c300, c100, c50, katus, gekis, misses, completed)
        == grade
    )


class TestStableDetail:
    @pytest.mark.asyncio
    async def test_lazer_custom_modes_are_rejected(
        self, mock_context: MockContext
    ) -> None:
        result = await scores_service.get_stable_score(mock_context, 30, 3)

        assert result == scores_service.ScoreError.INVALID_CUSTOM_MODE

    @pytest.mark.asyncio
    async def test_unknown_score_is_not_found(self, mock_context: MockContext) -> None:
        result = await scores_service.get_stable_score(mock_context, 30, 0)

        assert result == scores_service.ScoreError.SCORE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_hides_restricted_players(
        self, mock_mysql: MockMySQLAdapter, mock_context: MockContext
    ) -> None:
        mock_mysql.set_result(STABLE_QUERY, {**STABLE_ROW, "privileges": 2})

        result = await scores_service.get_stable_score(mock_context, 30, 0)

        assert result == scores_service.ScoreError.SCORE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_rank_is_one_past_the_players_ahead(
        self, mock_mysql: MockMySQLAdapter, mock_context: MockContext
    ) -> None:
        mock_mysql.set_result(STABLE_QUERY, dict(STABLE_ROW))
        mock_mysql.set_result(STABLE_RANK_QUERY, {"ahead": 2})

        result = await scores_service.get_stable_score(mock_context, 30, 0)

        assert not isinstance(result, scores_service.ScoreError)
        assert result.global_rank == 3

    @pytest.mark.asyncio
    async def test_no_rank_when_not_the_players_best(
        self, mock_mysql: MockMySQLAdapter, mock_context: MockContext
    ) -> None:
        mock_mysql.set_result(STABLE_QUERY, {**STABLE_ROW, "completed": 2})

        result = await scores_service.get_stable_score(mock_context, 30, 0)

        assert not isinstance(result, scores_service.ScoreError)
        assert result.global_rank is None
