"""Unit tests for the upload requests service."""

from __future__ import annotations

import pytest

from soumetsu_api.services import upload_requests
from soumetsu_api.services._common import is_success
from tests.conftest import MockContext
from tests.conftest import MockMySQLAdapter

PLAYER = 5
OPEN_LOOKUP = "SELECT user_id, status FROM upload_requests"

SCORE_ROW = {
    "id": 77,
    "beatmap_md5": "a" * 32,
    "player_id": PLAYER,
    "score": 1_000_000,
    "max_combo": 500,
    "full_combo": True,
    "mods": 0,
    "count_300": 500,
    "count_100": 0,
    "count_50": 0,
    "count_katus": 0,
    "count_gekis": 100,
    "count_misses": 0,
    "submitted_at": 1_700_000_000,
    "play_mode": 0,
    "completed": 3,
    "accuracy": 100.0,
    "pp": 400.0,
    "playtime": 120,
    "playback_rate": 1.0,
}


class TestVote:
    @pytest.mark.asyncio
    async def test_cannot_vote_on_own_request(
        self,
        mock_context: MockContext,
        mock_mysql: MockMySQLAdapter,
    ) -> None:
        mock_mysql.set_result(OPEN_LOOKUP, {"user_id": PLAYER, "status": 0})

        result = await upload_requests.vote(mock_context, PLAYER, 1, 1)

        assert result == upload_requests.UploadRequestError.CANNOT_VOTE

    @pytest.mark.asyncio
    async def test_cannot_vote_once_decided(
        self,
        mock_context: MockContext,
        mock_mysql: MockMySQLAdapter,
    ) -> None:
        mock_mysql.set_result(OPEN_LOOKUP, {"user_id": 9, "status": 1})

        result = await upload_requests.vote(mock_context, PLAYER, 1, 1)

        assert result == upload_requests.UploadRequestError.CANNOT_VOTE

    @pytest.mark.asyncio
    async def test_returns_the_new_counts(
        self,
        mock_context: MockContext,
        mock_mysql: MockMySQLAdapter,
    ) -> None:
        mock_mysql.set_result(OPEN_LOOKUP, {"user_id": 9, "status": 0})
        mock_mysql.set_result("FROM upload_request_votes WHERE", {"up": 2, "down": 1})

        result = await upload_requests.vote(mock_context, PLAYER, 1, -1)

        assert is_success(result)
        assert (result.up, result.down, result.mine) == (2, 1, -1)


class TestCreateRequest:
    @pytest.mark.asyncio
    async def test_rejects_someone_elses_score(
        self,
        mock_context: MockContext,
        mock_mysql: MockMySQLAdapter,
    ) -> None:
        mock_mysql.set_result("FROM scores", SCORE_ROW | {"player_id": 9})

        result = await upload_requests.create_request(
            mock_context,
            PLAYER,
            3,
            77,
            "",
            "Clean play",
        )

        assert result == upload_requests.UploadRequestError.SCORE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_limits_open_requests(
        self,
        mock_context: MockContext,
        mock_mysql: MockMySQLAdapter,
    ) -> None:
        mock_mysql.set_result("FROM scores", SCORE_ROW)
        mock_mysql.set_result(
            "FROM upload_requests WHERE user_id",
            upload_requests.MAX_OPEN_PER_USER,
        )

        result = await upload_requests.create_request(
            mock_context,
            PLAYER,
            3,
            77,
            "",
            "Clean play",
        )

        assert result == upload_requests.UploadRequestError.TOO_MANY_OPEN


class TestSkinLink:
    @pytest.mark.asyncio
    async def test_rejects_a_bad_skin_link(
        self,
        mock_context: MockContext,
        mock_mysql: MockMySQLAdapter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_mysql.set_result("FROM scores", SCORE_ROW)
        mock_mysql.set_result("FROM upload_requests WHERE user_id", 0)

        async def invalid(url: str) -> bool:
            return False

        monkeypatch.setattr(upload_requests.skins, "is_valid_skin_url", invalid)

        result = await upload_requests.create_request(
            mock_context,
            PLAYER,
            3,
            77,
            "https://example.com/not-a-skin",
            "Clean play",
        )

        assert result == upload_requests.UploadRequestError.INVALID_SKIN
