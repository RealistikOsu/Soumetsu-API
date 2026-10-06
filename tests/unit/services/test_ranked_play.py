from __future__ import annotations

from dataclasses import asdict
from datetime import UTC
from datetime import datetime

import pytest

from soumetsu_api.api.v2.ranked_play import MatchEventsResponse
from soumetsu_api.resources.ranked_play import MatchData
from soumetsu_api.resources.ranked_play import MatchRoundData
from soumetsu_api.resources.ranked_play import MatchScoreData
from soumetsu_api.services import is_error
from soumetsu_api.services import ranked_play
from soumetsu_api.services.ranked_play import RankedPlayError
from soumetsu_api.services.ranked_play import UserRef
from tests.conftest import MockContext
from tests.conftest import MockMySQLAdapter

START = datetime(2026, 10, 1, 12, 0, 0)

MATCH = MatchData(
    id=7,
    winner_user_id=None,
    status="ended",
    name="",
    started_at=START,
    ended_at=None,
)


def make_round(number: int, set_id: int | None, stars: float | None) -> MatchRoundData:
    return MatchRoundData(
        match_id=7,
        round=number,
        ruleset_id=0,
        started_at=START,
        ended_at=None,
        beatmap_id=number * 10,
        beatmapset_id=set_id,
        song_name="Artist - Title [Insane]" if set_id else None,
        ranked=1 if set_id else None,
        stars=stars,
        creator="Mapper" if set_id else None,
    )


def make_score(
    user_id: int, number: int, total: int, accuracy: float
) -> MatchScoreData:
    return MatchScoreData(
        round=number,
        user_id=user_id,
        total_score=total,
        accuracy=accuracy,
        max_combo=100,
        rank="A",
        passed=True,
        statistics="{}",
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            '{"great": 5, "ok": 2, "meh": 1, "miss": 3, "large_tick_hit": 9}',
            {"great": 5, "ok": 2, "meh": 1, "miss": 3},
        ),
        ('{"great": 5}', {"great": 5, "ok": 0, "meh": 0, "miss": 0}),
        ("", {"great": 0, "ok": 0, "meh": 0, "miss": 0}),
    ],
)
def test_parse_statistics(raw: str, expected: dict[str, int]) -> None:
    assert ranked_play.parse_statistics(raw) == expected


def test_beatmap_ref_splits_song_name() -> None:
    ref = ranked_play.beatmap_ref(make_round(1, 55, 5.4))

    assert (ref.artist, ref.title, ref.version) == ("Artist", "Title", "Insane")
    assert (ref.set_id, ref.creator, ref.star_rating) == (55, "Mapper", 5.4)


def test_beatmap_ref_survives_missing_beatmap() -> None:
    ref = ranked_play.beatmap_ref(make_round(2, None, None))

    assert ref.id == 20
    assert (ref.set_id, ref.artist, ref.title, ref.version, ref.creator) == (
        0,
        "",
        "",
        "",
        "",
    )
    assert ref.star_rating is None


def test_summary_star_range_and_covers() -> None:
    rounds = [
        make_round(1, 5, 4.2),
        make_round(2, None, None),
        make_round(3, 5, 6.1),
        make_round(4, 9, 0),
    ]

    summary = ranked_play.build_summary(MATCH, [], rounds)

    assert (summary.star_min, summary.star_max) == (4.2, 6.1)
    assert summary.cover_set_ids == [5, 9]
    assert summary.map_count == 4


def test_summary_without_rounds() -> None:
    summary = ranked_play.build_summary(MATCH, [], [])

    assert (summary.star_min, summary.star_max, summary.cover_set_ids) == (
        None,
        None,
        [],
    )


def test_summary_names_empty_match_after_players() -> None:
    players = [UserRef(1, "alice", "GB"), UserRef(2, "bob", "PL")]

    assert ranked_play.build_summary(MATCH, players, []).name == (
        "Ranked Play: alice vs bob"
    )
    assert ranked_play.build_summary(MATCH, [], []).name == "Ranked Play"
    named = MATCH.model_copy(update={"name": "Finals"})
    assert ranked_play.build_summary(named, players, []).name == "Finals"


def test_summary_dates_are_utc() -> None:
    summary = ranked_play.build_summary(MATCH, [], [])

    assert summary.started_at == START.replace(tzinfo=UTC)
    assert summary.ended_at is None


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
    ]

    result = ranked_play.rank_participants(players, scores)

    assert [p.user.id for p in result] == [2, 1, 3]
    assert [p.rank for p in result] == [1, 2, 3]
    assert (result[1].total_score, result[1].play_count) == (800, 2)
    assert result[1].accuracy == 92.78
    assert (result[2].total_score, result[2].accuracy, result[2].play_count) == (
        0,
        0.0,
        0,
    )


def test_round_detail_sorts_scores_and_skips_hidden_users() -> None:
    users = {1: UserRef(1, "alice", "GB"), 2: UserRef(2, "bob", "PL")}
    scores = [
        make_score(1, 1, 100, 90.0),
        make_score(2, 1, 200, 80.0),
        make_score(3, 1, 999, 70.0),
        make_score(1, 2, 5, 50.0),
    ]

    detail = ranked_play.round_detail(make_round(1, 5, 3.0), scores, users)

    assert [s.user.id for s in detail.scores] == [2, 1]
    assert detail.scores[0].statistics == {"great": 0, "ok": 0, "meh": 0, "miss": 0}


@pytest.mark.asyncio
async def test_unknown_match_is_not_found() -> None:
    ctx = MockContext(MockMySQLAdapter())

    result = await ranked_play.get_match(ctx, 404)

    assert is_error(result)
    assert result == RankedPlayError.MATCH_NOT_FOUND
    assert result.status_code() == 404

    result = await ranked_play.get_match_events(ctx, 404)
    assert result == RankedPlayError.MATCH_NOT_FOUND


def test_events_response_keeps_tagged_shapes() -> None:
    round_row = make_round(1, 5, 3.0)
    detail = ranked_play.round_detail(round_row, [], {})
    summary = ranked_play.build_summary(MATCH, [], [round_row])
    at = START.replace(tzinfo=UTC)
    result = ranked_play.MatchEventsResult(
        match=summary,
        events=[
            ranked_play.MatchEvent("joined", at, UserRef(1, "alice", "GB")),
            ranked_play.MatchEvent("round", at, round=detail),
            ranked_play.MatchEvent("round_ended", at, round=1),
            ranked_play.MatchEvent("disbanded", at),
        ],
    )

    dumped = MatchEventsResponse.model_validate(asdict(result)).model_dump(mode="json")

    assert [e["type"] for e in dumped["events"]] == [
        "joined",
        "round",
        "round_ended",
        "disbanded",
    ]
    assert dumped["events"][1]["round"]["number"] == 1
    assert dumped["events"][2] == {
        "type": "round_ended",
        "at": "2026-10-01T12:00:00Z",
        "user": None,
        "round": 1,
    }
    assert dumped["events"][3]["user"] is None
