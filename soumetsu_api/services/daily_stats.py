from __future__ import annotations

from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import override

from fastapi import status

from soumetsu_api.resources.daily_stats import DailyDayData
from soumetsu_api.resources.sessions import SessionData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import privileges

DAYS_PER_QUALIFYING_WEEK = 3


class DailyStatsError(ServiceError):
    USER_NOT_FOUND = "user_not_found"
    USER_RESTRICTED = "user_restricted"

    @override
    def service(self) -> str:
        return "daily_stats"

    @override
    def status_code(self) -> int:
        match self:
            case DailyStatsError.USER_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case DailyStatsError.USER_RESTRICTED:
                return status.HTTP_403_FORBIDDEN
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class DailyStatsResult:
    total_days: int
    current_daily_streak: int
    current_weekly_streak: int
    best_daily_streak: int
    best_weekly_streak: int
    top_10_placements: int
    top_50_placements: int


def streaks(periods: Collection[int], now: int) -> tuple[int, int]:
    """Current and best run of consecutive periods; the current run may still end one period before `now`."""
    current = 0
    cursor = now if now in periods else now - 1
    while cursor - current in periods:
        current += 1

    best = 0
    for start in periods:
        if start - 1 in periods:
            continue
        length = 1
        while start + length in periods:
            length += 1
        best = max(best, length)

    return current, best


def week_index(day: date) -> int:
    return (day.toordinal() - 1) // 7


def build_stats(days: list[DailyDayData], today: date) -> DailyStatsResult:
    played = {day.challenge_date.toordinal() for day in days}
    per_week = Counter(week_index(day.challenge_date) for day in days)
    qualifying = {
        week for week, count in per_week.items() if count >= DAYS_PER_QUALIFYING_WEEK
    }

    current_daily, best_daily = streaks(played, today.toordinal())
    current_weekly, best_weekly = streaks(qualifying, week_index(today))

    finalised = [day for day in days if day.finalised]
    return DailyStatsResult(
        total_days=len(days),
        current_daily_streak=current_daily,
        current_weekly_streak=current_weekly,
        best_daily_streak=best_daily,
        best_weekly_streak=best_weekly,
        top_10_placements=sum(day.placement == 2 for day in finalised),
        top_50_placements=sum(day.placement >= 1 for day in finalised),
    )


async def get_user_stats(
    ctx: AbstractContext,
    user_id: int,
    viewer: SessionData | None = None,
    today: date | None = None,
) -> DailyStatsError.OnSuccess[DailyStatsResult]:
    user = await ctx.users.find_by_id(user_id)
    if not user:
        return DailyStatsError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if not privileges.can_view(user.id, user_privs, viewer):
        return DailyStatsError.USER_RESTRICTED

    days = await ctx.daily_stats.list_days(user_id)
    return build_stats(days, today or datetime.now(UTC).date())
