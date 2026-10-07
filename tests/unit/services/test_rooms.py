from __future__ import annotations

from dataclasses import asdict
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

import pytest

from soumetsu_api.api.v2.rooms import DailyChallengeResponse
from soumetsu_api.api.v2.rooms import PlaylistDetailResponse
from soumetsu_api.api.v2.rooms import ScoresResponse
from soumetsu_api.resources.rooms import _STABLE_PASSED
from soumetsu_api.resources.rooms import STATUS_FILTERS
from soumetsu_api.resources.rooms import BestScoreData
from soumetsu_api.resources.rooms import LadderData
from soumetsu_api.resources.rooms import PercentileData
from soumetsu_api.resources.rooms import RoomData
from soumetsu_api.resources.rooms import RoomItemData
from soumetsu_api.resources.rooms import StableLadderData
from soumetsu_api.services import is_error
from soumetsu_api.services import rooms
from soumetsu_api.services.rooms import Mod
from soumetsu_api.services.rooms import RoomsError
from tests.conftest import MockContext
from tests.conftest import MockMySQLAdapter

CREATED = datetime(2026, 10, 1, 12, 0, 0)

ROOM = RoomData(
    id=3,
    name="Weekly",
    host_id=None,
    challenge_date=None,
    created_at=CREATED,
    ends_at=None,
    ended_at=None,
)


def make_item(
    item_id: int, stars: float | None, set_id: int | None = 5
) -> RoomItemData:
    return RoomItemData(
        room_id=3,
        item_id=item_id,
        beatmap_id=item_id * 10,
        ruleset_id=0,
        beatmapset_id=set_id,
        song_name="Artist - Title [Insane]" if set_id else None,
        ranked=1 if set_id else None,
        stars=stars,
        creator="Mapper" if set_id else None,
        required_mods='[{"acronym": "HD"}]',
        allowed_mods="[]",
        expired=False,
    )


def ladder_rows(count: int) -> list[PercentileData]:
    return [
        PercentileData(n=count, rn=rn, best=1000 - rn) for rn in range(1, count + 1)
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            '[{"acronym": "DT", "settings": {"speed_change": 1.3}}]',
            [Mod("DT", {"speed_change": 1.3})],
        ),
        ('[{"acronym": "HD"}]', [Mod("HD", {})]),
        ('[{"acronym": "HD", "settings": null}, {"settings": {}}, 4]', [Mod("HD", {})]),
        ([{"acronym": "NF", "settings": {}}], [Mod("NF", {})]),
        ("not json", []),
        ('{"acronym": "HD"}', []),
        ("", []),
        (None, []),
    ],
)
def test_parse_mods(raw: str | list | None, expected: list[Mod]) -> None:
    assert rooms.parse_mods(raw) == expected


@pytest.mark.parametrize(
    ("year", "month", "end"),
    [
        (2026, 10, date(2026, 11, 1)),
        (2026, 12, date(2027, 1, 1)),
        (2028, 2, date(2028, 3, 1)),
    ],
)
def test_month_bounds(year: int, month: int, end: date) -> None:
    assert rooms.month_bounds(year, month) == (date(year, month, 1), end)


def test_percentiles_without_players() -> None:
    assert rooms.pick_percentiles([]) == (0, None, None)


def test_percentiles_for_one_player() -> None:
    assert rooms.pick_percentiles(ladder_rows(1)) == (1, 999, 999)


@pytest.mark.parametrize(
    ("count", "top_10_position", "top_50_position"),
    [(2, 1, 1), (10, 1, 5), (11, 2, 6), (100, 10, 50), (101, 11, 51)],
)
def test_percentiles_pick_ceiling_positions(
    count: int,
    top_10_position: int,
    top_50_position: int,
) -> None:
    wanted = {top_10_position, top_50_position}
    rows = [row for row in ladder_rows(count) if row.rn in wanted]

    n, top_10, top_50 = rooms.pick_percentiles(rows)

    assert n == count
    assert top_10 == 1000 - top_10_position
    assert top_50 == 1000 - top_50_position


def test_shape_scores_uses_best_row_per_player() -> None:
    ladder = [
        LadderData(user_id=2, username="bob", country="PL", best=900, plays=3),
        LadderData(user_id=1, username="alice", country="GB", best=800, plays=1),
    ]
    bests = [
        BestScoreData(
            user_id=2,
            total_score=900,
            accuracy=0.98765,
            max_combo=400,
            rank="S",
            mods='[{"acronym": "HD"}]',
            created_at=CREATED,
        ),
        BestScoreData(
            user_id=2,
            total_score=900,
            accuracy=0.5,
            max_combo=1,
            rank="D",
            mods="[]",
            created_at=CREATED,
        ),
        BestScoreData(
            user_id=1,
            total_score=800,
            accuracy=1.0,
            max_combo=500,
            rank="X",
            mods=None,
            created_at=CREATED,
        ),
    ]

    scores = rooms.shape_scores(ladder, bests, offset=50)

    assert [s.rank for s in scores] == [51, 52]
    assert (scores[0].user.username, scores[0].play_count, scores[0].grade) == (
        "bob",
        3,
        "S",
    )
    assert (scores[0].accuracy, scores[0].max_combo) == (98.77, 400)
    assert scores[0].mods == [Mod("HD", {})]
    assert (scores[1].accuracy, scores[1].mods) == (100.0, [])


def test_summary_star_range_and_first_beatmap() -> None:
    items = [make_item(1, 4.2), make_item(2, None, set_id=None), make_item(3, 6.1)]

    summary = rooms.build_summary(ROOM, None, items, participants=4)

    assert (summary.star_min, summary.star_max) == (4.2, 6.1)
    assert (summary.item_count, summary.participants) == (3, 4)
    assert summary.first_beatmap is not None
    assert (summary.first_beatmap.id, summary.first_beatmap.title) == (10, "Title")
    assert summary.created_at == CREATED.replace(tzinfo=UTC)
    assert summary.ended_at is None


def test_summary_without_items() -> None:
    summary = rooms.build_summary(ROOM, None, [], participants=0)

    assert summary.first_beatmap is None
    assert (summary.star_min, summary.star_max, summary.item_count) == (None, None, 0)


def test_status_filters() -> None:
    assert STATUS_FILTERS["active"] == "ended_at IS NULL"
    assert STATUS_FILTERS["ended"] == "ended_at IS NOT NULL"


def test_playlist_response_keeps_shapes() -> None:
    items = [make_item(1, 5.0)]
    summary = rooms.build_summary(ROOM, None, items, participants=2)
    detail = rooms.PlaylistDetailResult(
        room=summary,
        items=[
            rooms.PlaylistItem(
                item_id=1,
                ruleset=0,
                beatmap=summary.first_beatmap,
                required_mods=rooms.parse_mods(items[0].required_mods),
                allowed_mods=[],
                expired=False,
                participants=2,
            ),
        ],
    )

    dumped = PlaylistDetailResponse.model_validate(asdict(detail)).model_dump(
        mode="json"
    )

    assert dumped["room"]["created_at"] == "2026-10-01T12:00:00Z"
    assert dumped["items"][0]["required_mods"] == [{"acronym": "HD", "settings": {}}]


def test_daily_response_serialises_date() -> None:
    window = rooms.window_of(date(2026, 10, 1))
    result = rooms.DailyChallengeResult(
        date=date(2026, 10, 1),
        starts_at=window[0],
        ends_at=window[1],
        beatmap=rooms.beatmap_ref(make_item(1, 5.0)),
        ruleset=0,
        required_mods=[],
        participants=0,
        stable_participants=3,
        stable_top_10_score=900000,
        stable_top_50_score=400000,
        top_10_score=None,
        top_50_score=None,
        room_id=None,
    )

    dumped = DailyChallengeResponse.model_validate(asdict(result)).model_dump(
        mode="json"
    )

    assert dumped["date"] == "2026-10-01"
    assert dumped["starts_at"] == "2026-10-01T00:00:00Z"
    assert dumped["ends_at"] == "2026-10-02T00:00:00Z"
    assert dumped["top_10_score"] is None
    assert dumped["stable_participants"] == 3
    assert dumped["stable_top_10_score"] == 900000
    assert dumped["stable_top_50_score"] == 400000


def test_stable_percentiles_use_the_same_cut_positions() -> None:
    rows = [PercentileData(n=25, rn=3, best=900), PercentileData(n=25, rn=13, best=500)]

    assert rooms.pick_percentiles(rows) == (25, 900, 500)


@pytest.mark.asyncio
async def test_unknown_day_is_not_found() -> None:
    ctx = MockContext(MockMySQLAdapter())

    result = await rooms.get_daily_challenge(ctx, date(2026, 10, 1))
    assert is_error(result)
    assert result == RoomsError.DAILY_CHALLENGE_NOT_FOUND
    assert result.status_code() == 404

    assert await rooms.get_daily_scores(ctx, date(2026, 10, 1), 1, 50) == (
        RoomsError.DAILY_CHALLENGE_NOT_FOUND
    )


@pytest.mark.asyncio
async def test_future_days_stay_secret_even_when_scheduled() -> None:
    mysql = MockMySQLAdapter()
    mysql.set_result("FROM lazer_daily_challenges d", {"beatmap_id": 1})
    ctx = MockContext(mysql)
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)

    assert await rooms.get_daily_challenge(ctx, tomorrow) == (
        RoomsError.DAILY_CHALLENGE_NOT_FOUND
    )
    for source in ("lazer", "stable"):
        assert await rooms.get_daily_scores(ctx, tomorrow, 1, 50, source) == (
            RoomsError.DAILY_CHALLENGE_NOT_FOUND
        )


@pytest.mark.asyncio
async def test_calendar_leaves_out_scheduled_future_days() -> None:
    today = datetime.now(UTC).date()
    mysql = MockMySQLAdapter()
    mysql.set_result(
        "FROM lazer_daily_challenges",
        [
            {"challenge_date": today},
            {"challenge_date": today + timedelta(days=1)},
        ],
    )

    result = await rooms.get_challenge_days(MockContext(mysql), today.year, today.month)

    assert [day.date for day in result.days] == [today]


def test_window_defaults_to_the_utc_day() -> None:
    start, end = rooms.window_of(date(2026, 10, 3))

    assert start == datetime(2026, 10, 3, tzinfo=UTC)
    assert end == datetime(2026, 10, 4, tzinfo=UTC)


def test_window_lasts_a_day_from_its_start() -> None:
    start, end = rooms.window_of(date(2026, 10, 3), datetime(2026, 10, 3, 18, 0))

    assert start == datetime(2026, 10, 3, 18, tzinfo=UTC)
    assert end == datetime(2026, 10, 4, 18, tzinfo=UTC)


def test_stable_scores_follow_a_custom_start() -> None:
    window = rooms.window_of(date(2026, 10, 3), datetime(2026, 10, 3, 12))

    start, end = rooms.window_bounds(window)

    assert end - start == 24 * 3600
    assert start == rooms.day_bounds(date(2026, 10, 3))[0] + 12 * 3600


@pytest.mark.asyncio
async def test_a_challenge_stays_secret_until_its_own_start() -> None:
    now = datetime.now(UTC)
    mysql = MockMySQLAdapter()
    mysql.set_result(
        "starts_at FROM lazer_daily_challenges",
        {
            "challenge_date": now.date(),
            "starts_at": (now + timedelta(hours=2)).replace(tzinfo=None),
        },
    )
    mysql.set_result("FROM lazer_daily_challenges d", {"beatmap_id": 1})
    ctx = MockContext(mysql)

    assert await rooms.get_daily_challenge(ctx, now.date()) == (
        RoomsError.DAILY_CHALLENGE_NOT_FOUND
    )


@pytest.mark.asyncio
async def test_unknown_room_is_not_found() -> None:
    ctx = MockContext(MockMySQLAdapter())

    assert await rooms.get_playlist(ctx, 404) == RoomsError.ROOM_NOT_FOUND
    assert await rooms.get_playlist_item_scores(ctx, 404, 1, 1, 50) == (
        RoomsError.ROOM_NOT_FOUND
    )


def stable_row(user_id: int, **overrides: int | float | str) -> StableLadderData:
    fields = {
        "user_id": user_id,
        "username": f"player{user_id}",
        "country": "GB",
        "score": 1_000_000,
        "accuracy": 98.7654,
        "max_combo": 300,
        "mods": 0,
        "playback_rate": 1.0,
        "count_300": 95,
        "count_100": 5,
        "count_50": 0,
        "count_katus": 4,
        "count_gekis": 20,
        "count_misses": 0,
        "plays": 2,
    }
    return StableLadderData(**(fields | overrides))


def test_day_bounds_cover_one_utc_day() -> None:
    start, end = rooms.day_bounds(date(2026, 10, 1))

    assert start == int(datetime(2026, 10, 1, tzinfo=UTC).timestamp())
    assert end - start == 86400
    assert rooms.day_bounds(date(2026, 10, 2))[0] == end


def test_shape_stable_scores() -> None:
    scores = rooms.shape_stable_scores(
        [stable_row(2), stable_row(1, accuracy=100.0, count_100=0, plays=1)],
        ruleset=0,
        offset=50,
    )

    assert [s.rank for s in scores] == [51, 52]
    assert (scores[0].user.username, scores[0].play_count) == ("player2", 2)
    assert (scores[0].accuracy, scores[0].max_combo) == (98.77, 300)
    assert (scores[0].grade, scores[1].grade) == ("S", "SS")
    assert scores[0].total_score == 1_000_000


def test_stable_mods_use_the_shared_conversion() -> None:
    [score] = rooms.shape_stable_scores(
        [stable_row(1, mods=8, playback_rate=1.0)], ruleset=0, offset=0
    )

    assert score.mods == [Mod("CL", {}), Mod("HD", {})]
    assert score.grade == "SH"


def test_stable_queries_are_no_mod_only() -> None:
    assert "s.mods = 0" in _STABLE_PASSED


def test_stable_response_shape() -> None:
    result = rooms.ScoresResult(
        total=1,
        scores=rooms.shape_stable_scores([stable_row(1)], ruleset=0, offset=0),
    )

    dumped = ScoresResponse.model_validate(asdict(result)).model_dump(mode="json")

    assert dumped["total"] == 1
    assert set(dumped["scores"][0]) == {
        "rank",
        "user",
        "total_score",
        "accuracy",
        "max_combo",
        "play_count",
        "grade",
        "mods",
    }
