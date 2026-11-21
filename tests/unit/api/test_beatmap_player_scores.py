"""A player's scores on a beatmap: the queries, who may see them and the two routes."""

from __future__ import annotations

import pytest
from soumetsu_api.api.v2 import beatmaps as routes
from soumetsu_api.api.v2.response import ServiceInterruptionException
from soumetsu_api.constants import CustomMode
from soumetsu_api.constants import GameMode
from soumetsu_api.resources import scores
from soumetsu_api.services import scores as scores_service
from tests.conftest import MockContext
from tests.conftest import MockMySQLAdapter

MD5 = "a" * 32

USER_ROW = {
    "id": 9,
    "username": "bob",
    "username_safe": "bob",
    "privileges": 1,
    "country": "PL",
    "registered_at": 1_600_000_000,
    "latest_activity": 1_700_000_000,
    "coins": 0,
}

BEATMAP_ROW = {
    "beatmap_id": 10,
    "beatmapset_id": 10,
    "beatmap_md5": MD5,
    "song_name": "a - b [c]",
    "ar": 8.0,
    "od": 8.0,
    "mode": 0,
    "difficulty_std": 5.0,
    "difficulty_taiko": 0.0,
    "difficulty_ctb": 0.0,
    "difficulty_mania": 0.0,
    "max_combo": 500,
    "hit_length": 90,
    "bpm": 180,
    "playcount": 0,
    "passcount": 0,
    "ranked": 2,
    "updated_at": 1_700_000_000,
    "ranked_status_frozen": 0,
    "mapper_id": 1,
    "dodge_the_beat": 0,
}

SCORE_ROW = {
    "id": 3,
    "beatmap_md5": MD5,
    "player_id": 9,
    "score": 900_000,
    "max_combo": 400,
    "full_combo": 0,
    "mods": 0,
    "count_300": 300,
    "count_100": 5,
    "count_50": 1,
    "count_katus": 0,
    "count_gekis": 0,
    "count_misses": 2,
    "submitted_at": 1_700_000_000,
    "play_mode": 0,
    "completed": 3,
    "accuracy": 98.5,
    "pp": 250.0,
    "playtime": 90_000,
    "playback_rate": 1.0,
    "mods_json": None,
    "player_db_id": 9,
    "username": "bob",
    "country": "PL",
}


class RecordingMySQL(MockMySQLAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.queries: list[str] = []
        self.values: list[dict] = []

    async def fetch_all(self, query, values=None):
        self.queries.append(query)
        self.values.append(values)
        return await super().fetch_all(query, values)


class Ctx(MockContext):
    session = None


def context(mysql: MockMySQLAdapter) -> Ctx:
    return Ctx(mysql)


class TestQueries:
    @pytest.mark.asyncio
    async def test_every_play_that_passed_comes_back_best_first(self) -> None:
        mysql = RecordingMySQL()
        mysql.set_result("FROM scores s", [dict(SCORE_ROW)])

        found = await scores.ScoresRepository(mysql).list_player_beatmap_scores(
            MD5, 9, 0, 0
        )

        assert [s.id for s in found] == [3]
        assert "s.completed >= 2" in mysql.queries[0]
        assert "ORDER BY s.pp DESC, s.id DESC" in mysql.queries[0]
        assert mysql.values[0]["player_id"] == 9

    @pytest.mark.asyncio
    async def test_a_dodge_the_beat_map_is_ordered_the_way_its_board_is(self) -> None:
        mysql = RecordingMySQL()

        await scores.ScoresRepository(mysql).list_player_beatmap_scores(
            MD5, 9, 2, 0, dodge_the_beat=True
        )

        assert "ORDER BY ROUND(s.accuracy, 4) DESC, s.score ASC" in mysql.queries[0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("custom_mode", "table"),
        [(CustomMode.VANILLA, "scores"), (CustomMode.RELAX, "scores_relax")],
    )
    async def test_relax_and_autopilot_read_their_own_table(
        self, custom_mode: CustomMode, table: str
    ) -> None:
        mysql = RecordingMySQL()

        await scores.ScoresRepository(mysql).list_player_beatmap_scores(
            MD5, 9, 0, custom_mode
        )

        assert f"FROM {table} s" in mysql.queries[0]

    @pytest.mark.asyncio
    async def test_lazer_reads_lazer_scores_best_first(self) -> None:
        mysql = RecordingMySQL()

        await scores.ScoresRepository(mysql).list_player_beatmap_scores(
            MD5, 9, 0, CustomMode.LAZER, limit=20, offset=40
        )

        assert "FROM lazer_scores l" in mysql.queries[0]
        assert "ORDER BY l.pp DESC, l.id DESC" in mysql.queries[0]
        assert mysql.values[0]["limit"] == 20
        assert mysql.values[0]["offset"] == 40


class TestService:
    @pytest.mark.asyncio
    async def test_an_unknown_player_is_not_found(self) -> None:
        result = await scores_service.get_player_beatmap_scores(
            context(MockMySQLAdapter()), MD5, 9, 0, 0
        )

        assert result == scores_service.ScoreError.USER_NOT_FOUND

    @pytest.mark.asyncio
    async def test_a_restricted_player_is_hidden_from_everyone_else(self) -> None:
        mysql = MockMySQLAdapter()
        mysql.set_result("FROM users", {**USER_ROW, "privileges": 2})

        result = await scores_service.get_player_beatmap_scores(
            context(mysql), MD5, 9, 0, 0, viewer=None
        )

        assert result == scores_service.ScoreError.USER_RESTRICTED

    @pytest.mark.asyncio
    async def test_the_page_size_is_capped(self) -> None:
        mysql = RecordingMySQL()
        mysql.set_result("FROM users", USER_ROW)

        await scores_service.get_player_beatmap_scores(
            context(mysql), MD5, 9, 0, 0, page=3, limit=500
        )

        assert mysql.values[0]["limit"] == 100
        assert mysql.values[0]["offset"] == 200


class TestRoutes:
    def player_with_scores(self) -> RecordingMySQL:
        mysql = RecordingMySQL()
        mysql.set_result("FROM beatmaps", dict(BEATMAP_ROW))
        mysql.set_result("FROM users", USER_ROW)
        mysql.set_result("FROM scores s", [dict(SCORE_ROW)])
        return mysql

    @pytest.mark.asyncio
    async def test_the_route_returns_the_scores_with_their_player(self) -> None:
        reply = await routes.get_player_beatmap_scores(
            context(self.player_with_scores()),
            10,
            9,
            GameMode.STD,
            CustomMode.VANILLA,
            page=1,
            limit=50,
        )

        assert reply.status_code == 200
        assert b'"data":[{' in reply.body
        assert b'"id":3' in reply.body

    @pytest.mark.asyncio
    async def test_a_player_with_no_scores_gets_an_empty_list(self) -> None:
        mysql = self.player_with_scores()
        mysql.set_result("FROM scores s", [])

        reply = await routes.get_player_beatmap_scores(
            context(mysql), 10, 9, GameMode.STD, CustomMode.VANILLA, page=1, limit=50
        )

        assert reply.status_code == 200
        assert b'"data":[]' in reply.body

    @pytest.mark.asyncio
    async def test_an_unknown_beatmap_is_a_404(self) -> None:
        mysql = self.player_with_scores()
        mysql.set_result("FROM beatmaps", None)

        with pytest.raises(ServiceInterruptionException) as error:
            await routes.get_player_beatmap_scores(
                context(mysql),
                10,
                9,
                GameMode.STD,
                CustomMode.VANILLA,
                page=1,
                limit=50,
            )

        assert error.value.response.status_code == 404
