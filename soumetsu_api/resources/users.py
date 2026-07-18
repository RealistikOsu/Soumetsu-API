from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.utilities.validation import safe_username


@dataclass
class ClanInfo:
    id: int
    name: str
    tag: str


class User(BaseModel):
    id: int
    username: str
    username_safe: str
    privileges: int
    country: str
    registered_at: int
    latest_activity: int
    coins: int


class UserForLogin(BaseModel):
    id: int
    username: str
    username_safe: str
    password_bcrypt: str
    privileges: int
    email: str


class UserRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def find_by_id(self, user_id: int) -> User | None:
        row = await self._mysql.fetch_one(
            """SELECT id, username, username_safe, privileges, country,
                      UNIX_TIMESTAMP(register_time) as registered_at,
                      COALESCE(UNIX_TIMESTAMP(latest_activity), 0) as latest_activity,
                      coins
               FROM users WHERE id = :id""",
            {"id": user_id},
        )
        return User(**row) if row else None

    async def find_by_username(self, username: str) -> User | None:
        username_safe = safe_username(username)
        row = await self._mysql.fetch_one(
            """SELECT id, username, username_safe, privileges, country,
                      UNIX_TIMESTAMP(register_time) as registered_at,
                      COALESCE(UNIX_TIMESTAMP(latest_activity), 0) as latest_activity,
                      coins
               FROM users WHERE username_safe = :username_safe""",
            {"username_safe": username_safe},
        )
        return User(**row) if row else None

    async def find_for_login(self, identifier: str) -> UserForLogin | None:
        if "@" in identifier:
            row = await self._mysql.fetch_one(
                """SELECT id, username, username_safe, password_bcrypt,
                          privileges, email
                   FROM users WHERE email = :email""",
                {"email": identifier},
            )
        else:
            username_safe = safe_username(identifier)
            row = await self._mysql.fetch_one(
                """SELECT id, username, username_safe, password_bcrypt,
                          privileges, email
                   FROM users WHERE username_safe = :username_safe""",
                {"username_safe": username_safe},
            )
        return UserForLogin(**row) if row else None

    async def username_exists(self, username: str) -> bool:
        username_safe = safe_username(username)
        count = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM users WHERE username_safe = :username_safe",
            {"username_safe": username_safe},
        )
        return count > 0

    async def email_exists(self, email: str) -> bool:
        count = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM users WHERE email = :email",
            {"email": email},
        )
        return count > 0

    async def username_in_history(self, username: str) -> bool:
        count = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM user_name_history WHERE username = :username",
            {"username": username},
        )
        return count > 0

    async def create(
        self,
        username: str,
        email: str,
        password_hash: str,
        privileges: int,
    ) -> int:
        username_safe = safe_username(username)
        user_id = await self._mysql.execute(
            """INSERT INTO users
               (username, username_safe, email, password_bcrypt, privileges)
               VALUES
               (:username, :username_safe, :email, :password_bcrypt, :privileges)""",
            {
                "username": username,
                "username_safe": username_safe,
                "email": email,
                "password_bcrypt": password_hash,
                "privileges": privileges,
            },
        )

        # Seed the tall user_stats table (one row per mode 0-7) and a settings row.
        for mode in range(8):
            await self._mysql.execute(
                "INSERT INTO user_stats (user_id, mode) VALUES (:user_id, :mode)",
                {"user_id": user_id, "mode": mode},
            )
        await self._mysql.execute(
            "INSERT INTO user_settings (user_id) VALUES (:user_id)",
            {"user_id": user_id},
        )

        return user_id

    async def update_country(self, user_id: int, country: str) -> None:
        await self._mysql.execute(
            "UPDATE users SET country = :country WHERE id = :id",
            {"country": country, "id": user_id},
        )

    async def get_privileges(self, user_id: int) -> int:
        result = await self._mysql.fetch_val(
            "SELECT privileges FROM users WHERE id = :id",
            {"id": user_id},
        )
        return result or 0

    async def search(self, query: str, limit: int, offset: int) -> list[User]:
        username_pattern = f"%{query}%"
        rows = await self._mysql.fetch_all(
            """SELECT id, username, username_safe, privileges, country,
                      UNIX_TIMESTAMP(register_time) as registered_at,
                      COALESCE(UNIX_TIMESTAMP(latest_activity), 0) as latest_activity,
                      coins
               FROM users
               WHERE username LIKE :pattern
               AND public = 1
               ORDER BY latest_activity DESC
               LIMIT :limit OFFSET :offset""",
            {"pattern": username_pattern, "limit": limit, "offset": offset},
        )
        return [User(**row) for row in rows]

    async def get_clan_info(self, user_id: int) -> ClanInfo | None:
        row = await self._mysql.fetch_one(
            """SELECT c.id, c.name, c.tag
               FROM clans c
               INNER JOIN users u ON u.clan_id = c.id
               WHERE u.id = :user_id""",
            {"user_id": user_id},
        )
        if not row:
            return None

        return ClanInfo(id=row["id"], name=row["name"], tag=row["tag"])

    async def update_username(
        self,
        user_id: int,
        new_username: str,
        old_username: str,
    ) -> None:
        new_username_safe = safe_username(new_username)

        await self._mysql.execute(
            """INSERT INTO user_name_history (user_id, username)
               VALUES (:user_id, :old_username)""",
            {
                "user_id": user_id,
                "old_username": old_username,
            },
        )

        await self._mysql.execute(
            "UPDATE users SET username = :username, username_safe = :username_safe WHERE id = :id",
            {
                "username": new_username,
                "username_safe": new_username_safe,
                "id": user_id,
            },
        )

    async def get_email(self, user_id: int) -> str | None:
        result = await self._mysql.fetch_val(
            "SELECT email FROM users WHERE id = :id",
            {"id": user_id},
        )
        return result

    async def get_password_hash(self, user_id: int) -> str | None:
        return await self._mysql.fetch_val(
            "SELECT password_bcrypt FROM users WHERE id = :id",
            {"id": user_id},
        )

    async def update_password(self, user_id: int, password_hash: str) -> None:
        await self._mysql.execute(
            "UPDATE users SET password_bcrypt = :password_hash WHERE id = :id",
            {"password_hash": password_hash, "id": user_id},
        )

    async def update_email(self, user_id: int, email: str) -> None:
        await self._mysql.execute(
            "UPDATE users SET email = :email WHERE id = :id",
            {"email": email, "id": user_id},
        )

    async def get_disabled_comments(self, user_id: int) -> bool:
        result = await self._mysql.fetch_val(
            "SELECT disabled_comments FROM users WHERE id = :id",
            {"id": user_id},
        )
        return bool(result) if result is not None else False

    async def update_disabled_comments(self, user_id: int, disabled: bool) -> None:
        await self._mysql.execute(
            "UPDATE users SET disabled_comments = :disabled WHERE id = :id",
            {"disabled": int(disabled), "id": user_id},
        )
