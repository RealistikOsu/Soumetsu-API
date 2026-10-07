from __future__ import annotations

from dataclasses import asdict
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from soumetsu_api.api.v2.multiplayer import MatchEventsResponse
from soumetsu_api.resources.multiplayer import GameData
from soumetsu_api.resources.multiplayer import GameScoreData
from soumetsu_api.resources.multiplayer import MatchData
from soumetsu_api.services import is_error
from soumetsu_api.services import multiplayer
from soumetsu_api.services.multiplayer import MatchEvent
from soumetsu_api.services.multiplayer import MultiplayerError
from soumetsu_api.services.ranked_play import UserRef
from tests.conftest import MockContext
from tests.conftest import MockMySQLAdapter

START = datetime(2026, 10, 1, 12, 0, 0)
UTC_START = START.replace(tzinfo=UTC)

MATCH = MatchData(
    id=7,
    name="Evening lobby",
    host_id=1,
    status="ended",
    created_at=START,
    ended_at=None,
)

HD = 8


def make_game(
    number: int,
    set_id: int | None = 5,
    stars: float | None = 4.0,
    mode: int = 0,
    ended: bool = True,
) -> GameData:
    started = START + timedelta(minutes=number)
    return GameData(
        match_id=7,
        game=number,
        mods=0,
        win_condition=0,
        team_type=0,
        started_at=started,
        ended_at=started + timedelta(minutes=3) if ended else None,
        beatmap_id=number * 10,
        beatmapset_id=set_id,
        song_name="Artist - Title [Insane]" if set_id else None,
        ranked=1 if set_id else None,
        stars=stars,
        creator="Mapper" if set_id else None,
        ruleset_id=mode,
    )


def make_score(
    user_id: int,
    game: int = 1,
    score: int = 1000,
    accuracy: float = 90.0,
    passed: bool = True,
    mods: int = 0,
    c300: int = 0,
    c100: int = 0,
    c50: int = 0,
    miss: int = 0,
) -> GameScoreData:
    return GameScoreData(
        game=game,
        user_id=user_id,
        team=0,
        score=score,
        accuracy=accuracy,
        max_combo=100,
        count_300=c300,
        count_100=c100,
        count_50=c50,
        count_miss=miss,
        count_geki=0,
        count_katu=0,
        mods=mods,
        passed=passed,
    )


@pytest.mark.parametrize(
    ("mode", "score", "grade"),
    [
        (0, make_score(1, c300=100), "SS"),
        (0, make_score(1, c300=100, mods=HD), "SSH"),
        (0, make_score(1, c300=95, c100=5), "S"),
        (0, make_score(1, c300=95, c100=5, mods=HD), "SH"),
        (0, make_score(1, c300=95, c100=3, c50=2), "A"),
        (0, make_score(1, c300=95, c100=4, miss=1), "A"),
        (0, make_score(1, c300=85, c100=15), "A"),
        (0, make_score(1, c300=75, c100=25), "B"),
        (0, make_score(1, c300=65, c100=35), "C"),
        (0, make_score(1, c300=50, c100=50), "D"),
        (0, make_score(1), "D"),
        (0, make_score(1, c300=100, passed=False), "F"),
        (1, make_score(1, c300=95, c100=5, c50=5), "S"),
        (1, make_score(1, c300=100, c50=9), "SS"),
        (2, make_score(2, accuracy=100.0), "SS"),
        (2, make_score(2, accuracy=98.5), "S"),
        (2, make_score(2, accuracy=96.0), "A"),
        (2, make_score(2, accuracy=91.0), "B"),
        (2, make_score(2, accuracy=86.0), "C"),
        (2, make_score(2, accuracy=80.0), "D"),
        (3, make_score(3, accuracy=96.0), "S"),
        (3, make_score(3, accuracy=96.0, mods=HD), "SH"),
        (3, make_score(3, accuracy=85.0), "B"),
        (3, make_score(3, accuracy=100.0, passed=False), "F"),
    ],
)
def test_grade_of(mode: int, score: GameScoreData, grade: str) -> None:
    assert multiplayer.grade_of(mode, score) == grade


def test_summary_star_range_and_covers() -> None:
    games = [
        make_game(1, 5, 4.2),
        make_game(2, None, None),
        make_game(3, 5, 6.1),
        make_game(4, 9, 0),
    ]

    summary = multiplayer.build_summary(MATCH, None, [], games)

    assert (summary.star_min, summary.star_max) == (4.2, 6.1)
    assert summary.cover_set_ids == [5, 9]
    assert summary.map_count == 4


def test_summary_without_games() -> None:
    summary = multiplayer.build_summary(MATCH, None, [], [])

    assert (summary.star_min, summary.star_max, summary.cover_set_ids) == (
        None,
        None,
        [],
    )
    assert summary.started_at == UTC_START
    assert summary.ended_at is None


def test_summary_caps_players() -> None:
    players = [UserRef(i, f"p{i}", "GB") for i in range(30)]

    summary = multiplayer.build_summary(MATCH, players[0], players, [])

    assert len(summary.players) == multiplayer.SUMMARY_PLAYER_CAP
    assert summary.host == players[0]


def test_rank_participants() -> None:
    players = [
        UserRef(1, "alice", "GB"),
        UserRef(2, "bob", "PL"),
        UserRef(3, "carol", "HU"),
    ]
    scores = [
        make_score(1, 1, 500, 90.0),
        make_score(1, 2, 300, 95.55),
        make_score(2, 1, 900, 99.0),
        make_score(9, 1, 5000, 99.0),
    ]

    result = multiplayer.rank_participants(players, scores)

    assert [p.user.id for p in result] == [2, 1, 3]
    assert [p.rank for p in result] == [1, 2, 3]
    assert (result[1].total_score, result[1].play_count) == (800, 2)
    assert result[1].accuracy == 92.78
    assert (result[2].total_score, result[2].accuracy, result[2].play_count) == (
        0,
        0.0,
        0,
    )


def test_game_detail_sorts_scores_and_skips_hidden_users() -> None:
    users = {1: UserRef(1, "alice", "GB"), 2: UserRef(2, "bob", "PL")}
    scores = [
        make_score(1, 1, 100, c300=10),
        make_score(2, 1, 200, passed=False),
        make_score(3, 1, 999),
        make_score(1, 2, 5),
    ]

    detail = multiplayer.game_detail(make_game(1), scores, users)

    assert [s.user.id for s in detail.scores] == [2, 1]
    assert [s.grade for s in detail.scores] == ["F", "SS"]
    assert detail.scores[1].statistics["count_300"] == 10
    assert detail.beatmap.mode == 0


def test_merge_events_orders_by_time_then_kind() -> None:
    alice = UserRef(1, "alice", "GB")
    games = [make_game(1), make_game(2, ended=False)]
    game_one_start = UTC_START + timedelta(minutes=1)
    simple = [
        MatchEvent("disbanded", UTC_START + timedelta(minutes=10)),
        MatchEvent("joined", game_one_start, alice),
        MatchEvent("joined", UTC_START, alice),
    ]

    events = multiplayer.merge_events(simple, games, [], {1: alice})

    assert [(e.type, e.game if e.type == "game_ended" else None) for e in events] == [
        ("joined", None),
        ("game", None),
        ("joined", None),
        ("game", None),
        ("game_ended", 1),
        ("disbanded", None),
    ]


@pytest.mark.asyncio
async def test_unknown_match_is_not_found() -> None:
    ctx = MockContext(MockMySQLAdapter())

    result = await multiplayer.get_match(ctx, 404)

    assert is_error(result)
    assert result == MultiplayerError.MATCH_NOT_FOUND
    assert result.status_code() == 404

    result = await multiplayer.get_match_events(ctx, 404)
    assert result == MultiplayerError.MATCH_NOT_FOUND


def test_events_response_keeps_tagged_shapes() -> None:
    game = make_game(1)
    alice = UserRef(1, "alice", "GB")
    detail = multiplayer.game_detail(game, [make_score(1, 1, 10, c300=1)], {1: alice})
    summary = multiplayer.build_summary(MATCH, alice, [alice], [game])
    result = multiplayer.MatchEventsResult(
        match=summary,
        events=[
            MatchEvent("joined", UTC_START, alice),
            MatchEvent("game", UTC_START, game=detail),
            MatchEvent("game_ended", UTC_START, game=1),
            MatchEvent("disbanded", UTC_START),
        ],
    )

    dumped = MatchEventsResponse.model_validate(asdict(result)).model_dump(mode="json")

    assert [e["type"] for e in dumped["events"]] == [
        "joined",
        "game",
        "game_ended",
        "disbanded",
    ]
    assert dumped["events"][1]["game"]["number"] == 1
    assert dumped["events"][1]["game"]["scores"][0]["grade"] == "SS"
    assert dumped["events"][2] == {
        "type": "game_ended",
        "at": "2026-10-01T12:00:00Z",
        "user": None,
        "game": 1,
    }
    assert dumped["events"][3]["user"] is None
    assert dumped["match"]["host"]["username"] == "alice"
