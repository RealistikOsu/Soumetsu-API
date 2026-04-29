from __future__ import annotations

from soumetsu_api.adapters.redis import RedisClient

ONLINE_USERS_KEY = "ripple:online_users"
REGISTERED_USERS_KEY = "ripple:registered_users"


class StatsRepository:
    __slots__ = ("_redis",)

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def get_online_users(self) -> int:
        return int(await self._redis.get(ONLINE_USERS_KEY) or 0)

    async def get_registered_users(self) -> int:
        return int(await self._redis.get(REGISTERED_USERS_KEY) or 0)

    async def increment_registered_users(self) -> None:
        await self._redis.incr(REGISTERED_USERS_KEY)
