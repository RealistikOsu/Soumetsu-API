from __future__ import annotations

from dataclasses import dataclass
from typing import override

from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError


class StatsError(ServiceError):
    UNKNOWN = "unknown"

    @override
    def service(self) -> str:
        return "stats"


@dataclass
class Stats:
    online_users: int
    registered_users: int


async def get_stats(ctx: AbstractContext) -> StatsError.OnSuccess[Stats]:
    online_users = await ctx.stats.get_online_users()
    registered_users = await ctx.stats.get_registered_users()
    return Stats(
        online_users=online_users,
        registered_users=registered_users,
    )
