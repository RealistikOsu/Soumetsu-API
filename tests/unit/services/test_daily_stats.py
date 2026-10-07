from __future__ import annotations

from datetime import date
from datetime import timedelta

import pytest

from soumetsu_api.api.v2.daily_stats import DailyStatsResponse
from soumetsu_api.resources.daily_stats import DailyDayData
from soumetsu_api.services import daily_stats
from soumetsu_api.services import is_error
from soumetsu_api.services.daily_stats import DailyStatsError
from tests.conftest import MockContext
from tests.conftest import MockMySQLAdapter

# A Wednesday, so the ISO week runs 5 to 11 October.
TODAY = date(2026, 10, 7)
USER_ROW = {
    "id": 7,
    "username": "alice",
    "username_safe": "alice",
    "privileges": 3,
    "country": "GB",
    "registered_at": 0,
    "latest_activity": 0,
    "coins": 0,
}


def played(
    *days: date,
    placement: int = 0,
    stable_placement: int = 0,
    finalised: bool = True,
) -> list[DailyDayData]:
    return [
        DailyDayData(
            challenge_date=d,
            placement=placement,
            stable_placement=stable_placement,
            finalised=finalised,
        )
        for d in days
    ]


def ago(days: int) -> date:
    return TODAY - timedelta(days=days)


def test_no_rows_gives_zeros() -> None:
    stats = daily_stats.build_stats([], TODAY)

    assert stats == daily_stats.DailyStatsResult(0, 0, 0, 0, 0, 0, 0)


@pytest.mark.parametrize(
    ("offsets", "current", "best"),
    [
        ([0], 1, 1),
        ([0, 1, 2], 3, 3),
        ([1, 2], 2, 2),
        ([2, 3], 0, 2),
        ([0, 2, 3, 4], 1, 3),
        ([0, 1, 5, 6, 7, 8], 2, 4),
    ],
)
def test_daily_streaks(offsets: list[int], current: int, best: int) -> None:
    stats = daily_stats.build_stats(played(*(ago(o) for o in offsets)), TODAY)

    assert stats.current_daily_streak == current
    assert stats.best_daily_streak == best
    assert stats.total_days == len(offsets)


def test_streak_crosses_month_and_year_boundaries() -> None:
    days = played(date(2025, 12, 30), date(2025, 12, 31), date(2026, 1, 1))

    assert daily_stats.build_stats(days, date(2026, 1, 1)).current_daily_streak == 3


def test_week_boundaries_are_monday_to_sunday() -> None:
    sunday, monday = date(2026, 10, 4), date(2026, 10, 5)

    assert daily_stats.week_index(sunday) + 1 == daily_stats.week_index(monday)
    assert daily_stats.week_index(monday) == daily_stats.week_index(date(2026, 10, 11))


def test_days_across_a_week_boundary_do_not_qualify_together() -> None:
    days = played(date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 5))

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.best_weekly_streak == 0


def test_current_week_counts_once_it_qualifies() -> None:
    days = played(date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30))
    days += played(date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7))

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.current_weekly_streak == 2
    assert stats.best_weekly_streak == 2


def test_weekly_streak_stays_alive_while_current_week_is_unfinished() -> None:
    days = played(date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23))
    days += played(date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30))
    days += played(date(2026, 10, 5), date(2026, 10, 6))

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.current_weekly_streak == 2
    assert stats.best_weekly_streak == 2


def test_weekly_streak_breaks_after_a_missed_week() -> None:
    days = played(date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23))
    days += played(date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7))

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.current_weekly_streak == 1
    assert stats.best_weekly_streak == 1


def test_weekly_streak_dead_when_last_week_missed_and_this_week_short() -> None:
    days = played(date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23))
    days += played(date(2026, 10, 5), date(2026, 10, 6))

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.current_weekly_streak == 0
    assert stats.best_weekly_streak == 1


def test_placements_count_finalised_days_only() -> None:
    days = played(ago(10), placement=2)
    days += played(ago(11), ago(12), placement=1)
    days += played(ago(13), placement=0)
    days += played(ago(0), placement=2, finalised=False)

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.top_10_placements == 1
    assert stats.top_50_placements == 3
    assert stats.total_days == 5


def test_stable_only_days_count_for_participation_and_streaks() -> None:
    days = played(ago(0), ago(2), ago(3))
    days += played(ago(1), stable_placement=1)

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.total_days == 4
    assert stats.current_daily_streak == 4
    assert stats.best_daily_streak == 4


def test_better_of_the_two_placements_is_used() -> None:
    days = played(ago(10), placement=2, stable_placement=1)
    days += played(ago(11), placement=1, stable_placement=2)
    days += played(ago(12), placement=0, stable_placement=1)

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.top_10_placements == 2
    assert stats.top_50_placements == 3


def test_day_with_both_ladders_counts_once_per_tier() -> None:
    days = played(ago(10), placement=2, stable_placement=1)

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.top_10_placements == 1
    assert stats.top_50_placements == 1


def test_unfinalised_stable_placement_does_not_count() -> None:
    days = played(ago(0), stable_placement=2, finalised=False)

    stats = daily_stats.build_stats(days, TODAY)

    assert stats.total_days == 1
    assert stats.top_10_placements == 0
    assert stats.top_50_placements == 0


@pytest.mark.asyncio
async def test_unknown_user_is_not_found() -> None:
    result = await daily_stats.get_user_stats(MockContext(MockMySQLAdapter()), 404)

    assert is_error(result)
    assert result == DailyStatsError.USER_NOT_FOUND
    assert result.status_code() == 404


@pytest.mark.asyncio
async def test_restricted_user_is_forbidden() -> None:
    mysql = MockMySQLAdapter()
    mysql.set_result("FROM users", {**USER_ROW, "privileges": 2})

    result = await daily_stats.get_user_stats(MockContext(mysql), 7)

    assert result == DailyStatsError.USER_RESTRICTED
    assert result.status_code() == 403


@pytest.mark.asyncio
async def test_player_without_rows_gets_zeros() -> None:
    mysql = MockMySQLAdapter()
    mysql.set_result("FROM users", USER_ROW)
    mysql.set_result("lazer_daily_challenge_days", [])

    result = await daily_stats.get_user_stats(MockContext(mysql), 7, today=TODAY)

    assert result == daily_stats.DailyStatsResult(0, 0, 0, 0, 0, 0, 0)


@pytest.mark.asyncio
async def test_rows_are_read_from_the_table() -> None:
    mysql = MockMySQLAdapter()
    mysql.set_result("FROM users", USER_ROW)
    mysql.set_result(
        "lazer_daily_challenge_days",
        [
            {
                "challenge_date": ago(0),
                "placement": 0,
                "stable_placement": 2,
                "finalised": 1,
            }
        ],
    )

    result = await daily_stats.get_user_stats(MockContext(mysql), 7, today=TODAY)

    assert result.current_daily_streak == 1
    assert result.top_10_placements == 1


def test_response_model_matches_result() -> None:
    result = daily_stats.build_stats(played(ago(0), placement=1), TODAY)

    body = DailyStatsResponse.model_validate(result.__dict__)

    assert list(body.model_dump()) == [
        "total_days",
        "current_daily_streak",
        "current_weekly_streak",
        "best_daily_streak",
        "best_weekly_streak",
        "top_10_placements",
        "top_50_placements",
    ]
    assert body.top_50_placements == 1
