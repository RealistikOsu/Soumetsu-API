from __future__ import annotations

import time

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.constants import MODE_SUFFIXES
from soumetsu_api.constants import STATS_TABLES
from soumetsu_api.utilities.validation import safe_username


class AdminRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def create_rap_log(
        self,
        user_id: int,
        text: str,
        through: str,
    ) -> int:
        return await self._mysql.execute(
            """INSERT INTO rap_logs (userid, text, datetime, through)
               VALUES (:user_id, :text, :datetime, :through)""",
            {
                "user_id": user_id,
                "text": text,
                "datetime": int(time.time()),
                "through": through,
            },
        )

    async def ban_user(self, user_id: int, reason: str = "") -> None:
        await self._mysql.execute(
            """UPDATE users SET privileges = privileges & ~3,
                               ban_datetime = :ban_time,
                               ban_reason = :reason
               WHERE id = :user_id""",
            {
                "user_id": user_id,
                "ban_time": str(int(time.time())),
                "reason": reason,
            },
        )

    async def restrict_user(self, user_id: int, reason: str = "") -> None:
        await self._mysql.execute(
            """UPDATE users SET privileges = privileges & ~1,
                               ban_datetime = :ban_time,
                               ban_reason = :reason
               WHERE id = :user_id""",
            {
                "user_id": user_id,
                "ban_time": str(int(time.time())),
                "reason": reason,
            },
        )

    async def unrestrict_user(self, user_id: int) -> None:
        await self._mysql.execute(
            """UPDATE users SET privileges = privileges | 3,
                               ban_datetime = '0',
                               ban_reason = ''
               WHERE id = :user_id""",
            {"user_id": user_id},
        )

    async def update_user(
        self,
        user_id: int,
        username: str | None = None,
        email: str | None = None,
        country: str | None = None,
        silence_end: int | None = None,
        notes: str | None = None,
    ) -> None:
        updates = []
        params: dict[str, int | str] = {"user_id": user_id}

        if username is not None:
            updates.append("username = :username")
            updates.append("username_safe = :username_safe")
            params["username"] = username
            params["username_safe"] = safe_username(username)

        if email is not None:
            updates.append("email = :email")
            params["email"] = email

        if country is not None:
            updates.append("country = :country")
            params["country"] = country

        if silence_end is not None:
            updates.append("silence_end = :silence_end")
            params["silence_end"] = silence_end

        if notes is not None:
            updates.append("notes = :notes")
            params["notes"] = notes

        if not updates:
            return

        query = f"UPDATE users SET {', '.join(updates)} WHERE id = :user_id"
        await self._mysql.execute(query, params)

    async def wipe_user_stats(
        self,
        user_id: int,
        mode: int | None = None,
        custom_mode: int = 0,
    ) -> None:
        table = STATS_TABLES[custom_mode]

        if mode is not None:
            suffix = MODE_SUFFIXES[mode]
            await self._mysql.execute(
                f"""UPDATE {table} SET
                    pp_{suffix} = 0,
                    ranked_score_{suffix} = 0,
                    total_score_{suffix} = 0,
                    playcount_{suffix} = 0,
                    avg_accuracy_{suffix} = 0,
                    total_hits_{suffix} = 0,
                    playtime_{suffix} = 0,
                    max_combo_{suffix} = 0,
                    replays_watched_{suffix} = 0,
                    level_{suffix} = 1
                    WHERE id = :user_id""",
                {"user_id": user_id},
            )
        else:
            for m in range(4):
                suffix = MODE_SUFFIXES[m]
                await self._mysql.execute(
                    f"""UPDATE {table} SET
                        pp_{suffix} = 0,
                        ranked_score_{suffix} = 0,
                        total_score_{suffix} = 0,
                        playcount_{suffix} = 0,
                        avg_accuracy_{suffix} = 0,
                        total_hits_{suffix} = 0,
                        playtime_{suffix} = 0,
                        max_combo_{suffix} = 0,
                        replays_watched_{suffix} = 0,
                        level_{suffix} = 1
                        WHERE id = :user_id""",
                    {"user_id": user_id},
                )
