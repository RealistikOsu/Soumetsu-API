"""Unit tests for osu!lazer scores in the scores repository."""

from __future__ import annotations

import pytest

from soumetsu_api.constants import STATS_TABLES
from soumetsu_api.constants import CustomMode
from soumetsu_api.constants import is_valid_custom_mode
from soumetsu_api.resources import scores
from soumetsu_api.resources.leaderboard import _build_leaderboard_key
from soumetsu_api.services import scores as scores_service
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
            "rn": 1,
        }
        mysql = RecordingMySQL()
        mysql.set_result("ROW_NUMBER()", [row])

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
