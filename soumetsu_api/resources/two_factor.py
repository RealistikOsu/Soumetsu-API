from __future__ import annotations

import json
from dataclasses import dataclass

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.adapters.redis import RedisClient
from soumetsu_api.utilities import crypto

CHALLENGE_PREFIX = "soumetsuapi:2fa_challenge:"
SETUP_PREFIX = "soumetsuapi:2fa_setup:"
USED_PREFIX = "soumetsuapi:2fa_used:"
CHALLENGE_TTL_SECONDS = 5 * 60
SETUP_TTL_SECONDS = 30 * 60
MAX_ATTEMPTS = 5


@dataclass
class TwoFactorData:
    user_id: int
    secret: str
    confirmed: bool


@dataclass
class LoginChallenge:
    user_id: int
    privileges: int
    ip_address: str
    attempts: int


class TwoFactorRepository:
    __slots__ = ("_mysql", "_redis")

    def __init__(self, mysql: ImplementsMySQL, redis: RedisClient) -> None:
        self._mysql = mysql
        self._redis = redis

    async def get(self, user_id: int) -> TwoFactorData | None:
        row = await self._mysql.fetch_one(
            """SELECT user_id, secret, confirmed
               FROM user_totp WHERE user_id = :user_id""",
            {"user_id": user_id},
        )
        if not row:
            return None
        return TwoFactorData(
            user_id=row["user_id"],
            secret=row["secret"],
            confirmed=bool(row["confirmed"]),
        )

    async def start(self, user_id: int, secret: str, now: int) -> None:
        await self._mysql.execute(
            """INSERT INTO user_totp (user_id, secret, confirmed, created_at)
               VALUES (:user_id, :secret, 0, :now)
               ON DUPLICATE KEY UPDATE secret = VALUES(secret), confirmed = 0,
                   created_at = VALUES(created_at)""",
            {"user_id": user_id, "secret": secret, "now": now},
        )

    async def confirm(self, user_id: int) -> None:
        await self._mysql.execute(
            "UPDATE user_totp SET confirmed = 1 WHERE user_id = :user_id",
            {"user_id": user_id},
        )

    # A code (one 30 second step) is accepted once, even if two logins race for it; the key outlives the
    # window in which that code could still be valid.
    async def use_step(self, user_id: int, step: int) -> bool:
        used = await self._redis.set(
            f"{USED_PREFIX}{user_id}:{step}", 1, nx=True, ex=150,
        )
        return bool(used)

    async def delete(self, user_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM user_totp WHERE user_id = :user_id",
            {"user_id": user_id},
        )
        await self._mysql.execute(
            "DELETE FROM user_totp_recovery WHERE user_id = :user_id",
            {"user_id": user_id},
        )

    async def replace_recovery_codes(self, user_id: int, hashes: list[str]) -> None:
        await self._mysql.execute(
            "DELETE FROM user_totp_recovery WHERE user_id = :user_id",
            {"user_id": user_id},
        )
        for code_hash in hashes:
            await self._mysql.execute(
                """INSERT INTO user_totp_recovery (user_id, code_hash)
                   VALUES (:user_id, :code_hash)""",
                {"user_id": user_id, "code_hash": code_hash},
            )

    async def use_recovery_code(self, user_id: int, code_hash: str, now: int) -> bool:
        row = await self._mysql.fetch_one(
            """SELECT id FROM user_totp_recovery
               WHERE user_id = :user_id AND code_hash = :code_hash AND used_at IS NULL""",
            {"user_id": user_id, "code_hash": code_hash},
        )
        if not row:
            return False
        # The lock makes two logins racing for the same code see one success between them.
        if not await self._redis.set(
            f"{USED_PREFIX}recovery:{row['id']}", 1, nx=True, ex=60,
        ):
            return False
        await self._mysql.execute(
            "UPDATE user_totp_recovery SET used_at = :now WHERE id = :id",
            {"id": row["id"], "now": now},
        )
        return True

    async def recovery_codes_left(self, user_id: int) -> int:
        return await self._mysql.fetch_val(
            """SELECT COUNT(*) FROM user_totp_recovery
               WHERE user_id = :user_id AND used_at IS NULL""",
            {"user_id": user_id},
        )

    async def create_challenge(
        self, user_id: int, privileges: int, ip_address: str,
    ) -> str:
        token = crypto.generate_token(32)
        challenge = LoginChallenge(user_id, privileges, ip_address, attempts=0)
        await self._redis.set(
            CHALLENGE_PREFIX + crypto.hash_token_sha256(token),
            json.dumps(challenge.__dict__),
            ex=CHALLENGE_TTL_SECONDS,
        )
        return token

    async def get_challenge(self, token: str) -> LoginChallenge | None:
        data = await self._redis.get(CHALLENGE_PREFIX + crypto.hash_token_sha256(token))
        return LoginChallenge(**json.loads(data)) if data else None

    # A wrong code costs an attempt; after MAX_ATTEMPTS the challenge is gone and the password is needed again.
    async def fail_challenge(self, token: str, challenge: LoginChallenge) -> None:
        key = CHALLENGE_PREFIX + crypto.hash_token_sha256(token)
        challenge.attempts += 1
        if challenge.attempts >= MAX_ATTEMPTS:
            await self._redis.delete(key)
            return
        await self._redis.set(key, json.dumps(challenge.__dict__), keepttl=True)

    async def end_challenge(self, token: str) -> None:
        await self._redis.delete(CHALLENGE_PREFIX + crypto.hash_token_sha256(token))

    async def create_setup_token(self, user_id: int) -> str:
        token = crypto.generate_token(32)
        await self._redis.set(
            SETUP_PREFIX + crypto.hash_token_sha256(token),
            str(user_id),
            ex=SETUP_TTL_SECONDS,
        )
        return token

    async def take_setup_token(self, token: str) -> int | None:
        key = SETUP_PREFIX + crypto.hash_token_sha256(token)
        user_id = await self._redis.get(key)
        if user_id is None:
            return None
        await self._redis.delete(key)
        return int(user_id)
