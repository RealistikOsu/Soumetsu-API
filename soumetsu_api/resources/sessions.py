from __future__ import annotations

import json
import time
from dataclasses import dataclass

from soumetsu_api import settings
from soumetsu_api.adapters.redis import RedisClient
from soumetsu_api.utilities import crypto

SESSION_KEY_PREFIX = "soumetsuapi:session:"
USER_SESSIONS_PREFIX = "soumetsuapi:user_sessions:"


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

        session_key = f"{SESSION_KEY_PREFIX}{token_hash}"
        user_sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"

        # Use pipeline for atomic operations
        pipe = self._redis.pipeline()
        pipe.set(
            session_key,
            json.dumps(session.__dict__),
            ex=settings.SESSION_TTL_SECONDS,
        )
        pipe.sadd(user_sessions_key, token_hash)
        pipe.expire(user_sessions_key, settings.SESSION_TTL_SECONDS)
        await pipe.execute()

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
        session_key = f"{SESSION_KEY_PREFIX}{token_hash}"

        # Get session to find user_id for index cleanup
        data = await self._redis.get(session_key)
        if data:
            session_dict = json.loads(data)
            user_id = session_dict.get("user_id")
            if user_id:
                user_sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"
                await self._redis.srem(user_sessions_key, token_hash)

        result = await self._redis.delete(session_key)
        return result > 0

    async def delete_all_for_user(self, user_id: int) -> int:
        user_sessions_key = f"{USER_SESSIONS_PREFIX}{user_id}"
        token_hashes = await self._redis.smembers(user_sessions_key)

        if not token_hashes:
            return 0

        # Build list of session keys to delete
        session_keys = [f"{SESSION_KEY_PREFIX}{th}" for th in token_hashes]

        # Delete all sessions and the index in one pipeline
        pipe = self._redis.pipeline()
        for key in session_keys:
            pipe.delete(key)
        pipe.delete(user_sessions_key)
        await pipe.execute()

        return len(token_hashes)
