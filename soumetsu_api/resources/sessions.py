from __future__ import annotations

import json
import time
from dataclasses import dataclass

from soumetsu_api import settings
from soumetsu_api.adapters.redis import RedisClient
from soumetsu_api.utilities import crypto

SESSION_KEY_PREFIX = "session:"


@dataclass
class SessionData:
    user_id: int
    privileges: int
    created_at: int
    expires_at: int
    ip_address: str


class SessionRepository:
    __slots__ = ("_redis",)

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def create(
        self,
        user_id: int,
        privileges: int,
        ip_address: str,
    ) -> str:
        token = crypto.generate_token(32)
        token_hash = crypto.hash_token_sha256(token)

        now = int(time.time())
        session = SessionData(
            user_id=user_id,
            privileges=privileges,
            created_at=now,
            expires_at=now + settings.SESSION_TTL_SECONDS,
            ip_address=ip_address,
        )

        key = f"{SESSION_KEY_PREFIX}{token_hash}"
        await self._redis.set(
            key,
            json.dumps(session.__dict__),
            ex=settings.SESSION_TTL_SECONDS,
        )

        return token

    async def get(self, token: str) -> SessionData | None:
        token_hash = crypto.hash_token_sha256(token)
        key = f"{SESSION_KEY_PREFIX}{token_hash}"

        data = await self._redis.get(key)
        if not data:
            return None

        session_dict = json.loads(data)
        session = SessionData(**session_dict)

        if session.expires_at < int(time.time()):
            await self._redis.delete(key)
            return None

        if settings.SESSION_SLIDING_WINDOW:
            session.expires_at = int(time.time()) + settings.SESSION_TTL_SECONDS
            await self._redis.set(
                key,
                json.dumps(session.__dict__),
                ex=settings.SESSION_TTL_SECONDS,
            )

        return session

    async def delete(self, token: str) -> bool:
        token_hash = crypto.hash_token_sha256(token)
        key = f"{SESSION_KEY_PREFIX}{token_hash}"
        result = await self._redis.delete(key)
        return result > 0

    async def delete_all_for_user(self, user_id: int) -> int:
        pattern = f"{SESSION_KEY_PREFIX}*"
        deleted = 0

        async for key in self._redis.scan_iter(match=pattern):
            data = await self._redis.get(key)
            if data:
                session_dict = json.loads(data)
                if session_dict.get("user_id") == user_id:
                    await self._redis.delete(key)
                    deleted += 1

        return deleted
