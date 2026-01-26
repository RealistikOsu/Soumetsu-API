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
    password_md5: str
    password_version: int
    privileges: int
    email: str


class UserRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def find_by_id(self, user_id: int) -> User | None:
        row = await self._mysql.fetch_one(
            """SELECT id, username, username_safe, privileges, country,
                      register_datetime as registered_at, latest_activity, coins
               FROM users WHERE id = :id""",
            {"id": user_id},
        )
        return User(**row) if row else None

    async def find_by_username(self, username: str) -> User | None:
        username_safe = safe_username(username)
        row = await self._mysql.fetch_one(
            """SELECT id, username, username_safe, privileges, country,
                      register_datetime as registered_at, latest_activity, coins
               FROM users WHERE username_safe = :username_safe""",
            {"username_safe": username_safe},
        )
        return User(**row) if row else None

    async def find_for_login(self, identifier: str) -> UserForLogin | None:
        if "@" in identifier:
            row = await self._mysql.fetch_one(
                """SELECT id, username, username_safe, password_md5,
                          password_version, privileges, email
                   FROM users WHERE email = :email""",
                {"email": identifier},
            )
        else:
            username_safe = safe_username(identifier)
            row = await self._mysql.fetch_one(
                """SELECT id, username, username_safe, password_md5,
                          password_version, privileges, email
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
        username_safe = safe_username(username)
        count = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM user_name_history WHERE username_safe = :username_safe",
            {"username_safe": username_safe},
        )
        return count > 0

    async def create(
        self,
        username: str,
        email: str,
        password_hash: str,
        api_key: str,
        privileges: int,
        registered_at: int,
    ) -> int:
        username_safe = safe_username(username)
        result = await self._mysql.execute(
            """INSERT INTO users
               (username, username_safe, email, password_md5, salt, api_key,
                privileges, register_datetime, password_version)
               VALUES
               (:username, :username_safe, :email, :password_md5, '', :api_key,
                :privileges, :registered_at, 2)""",
            {
                "username": username,
                "username_safe": username_safe,
                "email": email,
                "password_md5": password_hash,
                "api_key": api_key,
                "privileges": privileges,
                "registered_at": registered_at,
            },
        )
        return result

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
                      register_datetime as registered_at, latest_activity, coins
               FROM users
               WHERE username LIKE :pattern
               AND privileges & 1 = 1
               ORDER BY latest_activity DESC
               LIMIT :limit OFFSET :offset""",
            {"pattern": username_pattern, "limit": limit, "offset": offset},
        )
        return [User(**row) for row in rows]

    async def get_clan_info(self, user_id: int) -> ClanInfo | None:
        row = await self._mysql.fetch_one(
            """SELECT c.id, c.name, c.tag
               FROM clans c
               INNER JOIN user_clans uc ON c.id = uc.clan
               WHERE uc.user = :user_id""",
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
        old_username_safe = safe_username(old_username)

        await self._mysql.execute(
            """INSERT INTO user_name_history (user_id, previous_username, previous_username_safe, changed_datetime)
               VALUES (:user_id, :old_username, :old_username_safe, UNIX_TIMESTAMP())""",
            {
                "user_id": user_id,
                "old_username": old_username,
                "old_username_safe": old_username_safe,
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

        for table in ("users_stats", "rx_stats", "ap_stats"):
            await self._mysql.execute(
                f"UPDATE {table} SET username = :username WHERE id = :id",
                {"username": new_username, "id": user_id},
            )

    async def get_discord_id(self, user_id: int) -> int | None:
        result = await self._mysql.fetch_val(
            "SELECT discordid FROM users WHERE id = :id",
            {"id": user_id},
        )
        return result if result else None

    async def unlink_discord(self, user_id: int) -> None:
        await self._mysql.execute(
            "UPDATE users SET discordid = 0, discord_username = '' WHERE id = :id",
            {"id": user_id},
        )

    async def get_email(self, user_id: int) -> str | None:
        result = await self._mysql.fetch_val(
            "SELECT email FROM users WHERE id = :id",
            {"id": user_id},
        )
        return result

    async def get_password_hash(self, user_id: int) -> tuple[str, int] | None:
        row = await self._mysql.fetch_one(
            "SELECT password_md5, password_version FROM users WHERE id = :id",
            {"id": user_id},
        )
        if not row:
            return None
        return row["password_md5"], row["password_version"]

    async def update_password(self, user_id: int, password_hash: str) -> None:
        await self._mysql.execute(
            "UPDATE users SET password_md5 = :password_hash, password_version = 2 WHERE id = :id",
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
