"""Unit tests for osu!lazer scores in the scores repository."""

from __future__ import annotations

import pytest

from soumetsu_api.constants import CustomMode
from soumetsu_api.resources import scores
from soumetsu_api.resources.leaderboard import _build_leaderboard_key
from soumetsu_api.services import scores as scores_service
from tests.conftest import MockContext
from tests.conftest import MockMySQLAdapter

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


class TestRepository:
    @pytest.mark.asyncio
    async def test_find_by_id_reads_lazer_scores(
        self, mock_mysql: MockMySQLAdapter
    ) -> None:
        mock_mysql.set_result("FROM lazer_scores", dict(LAZER_ROW))

        score = await scores.ScoresRepository(mock_mysql).find_by_id(
            12, CustomMode.LAZER
        )

        assert score is not None
        assert score.id == 12

    @pytest.mark.asyncio
    async def test_lazer_best_plays_carry_their_beatmap(
        self, mock_mysql: MockMySQLAdapter
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
        mock_mysql.set_result("ROW_NUMBER()", [row])

        best = await scores.ScoresRepository(mock_mysql).list_player_best(
            5, 0, CustomMode.LAZER
        )

        assert [(s.id, s.beatmap_id, s.pp) for s in best] == [(12, 7, 321.5)]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["list_player_firsts", "list_player_pinned"])
    async def test_lazer_has_no_firsts_or_pins(
        self, mock_mysql: MockMySQLAdapter, method: str
    ) -> None:
        repository = scores.ScoresRepository(mock_mysql)

        assert await getattr(repository, method)(5, 0, CustomMode.LAZER) == []


@pytest.mark.asyncio
async def test_lazer_scores_cannot_be_pinned(mock_context: MockContext) -> None:
    result = await scores_service.pin_score(mock_context, 5, 12, CustomMode.LAZER)

    assert result == scores_service.ScoreError.INVALID_CUSTOM_MODE


def test_lazer_leaderboard_keys() -> None:
    assert _build_leaderboard_key(CustomMode.LAZER, 3) == (
        "ripple:leaderboard_lazer:mania"
    )
    assert _build_leaderboard_key(CustomMode.LAZER, 0, "GB") == (
        "ripple:leaderboard_lazer:std:gb"
    )
