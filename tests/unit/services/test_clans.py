from __future__ import annotations

import pytest

from soumetsu_api.services import clans
from tests.conftest import MockContext
from tests.conftest import MockMySQLAdapter


def member(clan_id: int, name: str, pp: int, score: int = 100) -> dict[str, object]:
    return {
        "clan_id": clan_id,
        "name": name,
        "tag": name[:3].upper(),
        "pp": pp,
        "ranked_score": score,
        "total_score": score * 2,
        "playcount": 10,
        "replays_watched": 0,
        "total_hits": 0,
    }


@pytest.mark.asyncio
async def test_leaderboard_ranks_clans_by_weighted_member_pp() -> None:
    mysql = MockMySQLAdapter()
    mysql.set_result(
        "FROM clans c",
        [
            member(1, "alpha", 1000),
            member(1, "alpha", 1000),
            member(2, "bravo", 1500),
        ],
    )
    mysql.set_result(
        "GROUP BY clan",
        [{"clan": 1, "n": 3}, {"clan": 2, "n": 1}],
    )

    board = await clans.get_clan_leaderboard(MockContext(mysql), 0, 0, 1, 50)

    assert isinstance(board, list)
    assert [(e.name, e.rank, e.chosen_mode.pp) for e in board] == [
        ("alpha", 1, 1950),
        ("bravo", 2, 1500),
    ]
    assert board[0].chosen_mode.ranked_score == 200
    assert board[0].member_count == 3


@pytest.mark.asyncio
async def test_leaderboard_pages() -> None:
    mysql = MockMySQLAdapter()
    mysql.set_result(
        "FROM clans c",
        [member(i, f"clan{i}", 1000 - i) for i in range(1, 6)],
    )

    board = await clans.get_clan_leaderboard(MockContext(mysql), 0, 0, 2, 2)

    assert isinstance(board, list)
    assert [(e.id, e.rank) for e in board] == [(3, 3), (4, 4)]
