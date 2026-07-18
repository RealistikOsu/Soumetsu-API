from __future__ import annotations

import time

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.constants import combined_mode
from soumetsu_api.utilities.validation import safe_username

# infractions.type (see migrate_data/steps/20_infractions.sql)
_INFRACTION_RESTRICT = 0
_INFRACTION_BAN = 1
_INFRACTION_SILENCE = 2

# columns to zero out when wiping a tall user_stats row
_WIPE_STATS = (
    "ranked_score = 0, total_score = 0, pp = 0, accuracy = 0, playcount = 0, "
    "playtime = 0, total_hits = 0, max_combo = 0, replays_watched = 0, level = 1, "
    "count_ssh = 0, count_ss = 0, count_sh = 0, count_s = 0, count_a = 0"
)

# valid vanilla modes per custom mode (used when wiping "all" modes)
_MODES_FOR_CUSTOM = {0: (0, 1, 2, 3), 1: (0, 1, 2), 2: (0,)}


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
        # created_at defaults to CURRENT_TIMESTAMP in the clean schema.
        return await self._mysql.execute(
            """INSERT INTO rap_logs (user_id, text, through)
               VALUES (:user_id, :text, :through)""",
            {"user_id": user_id, "text": text, "through": through},
        )

    async def ban_user(self, user_id: int, reason: str = "") -> None:
        await self._mysql.execute(
            "UPDATE users SET public = 0 WHERE id = :user_id",
            {"user_id": user_id},
        )
        await self._mysql.execute(
            """INSERT INTO infractions (user_id, type, reason, active)
               VALUES (:user_id, :type, :reason, 1)""",
            {"user_id": user_id, "type": _INFRACTION_BAN, "reason": reason},
        )

    async def restrict_user(self, user_id: int, reason: str = "") -> None:
        await self._mysql.execute(
            "UPDATE users SET public = 0 WHERE id = :user_id",
            {"user_id": user_id},
        )
        await self._mysql.execute(
            """INSERT INTO infractions (user_id, type, reason, active)
               VALUES (:user_id, :type, :reason, 1)""",
            {"user_id": user_id, "type": _INFRACTION_RESTRICT, "reason": reason},
        )

    async def unrestrict_user(self, user_id: int) -> None:
        await self._mysql.execute(
            "UPDATE users SET public = 1 WHERE id = :user_id",
            {"user_id": user_id},
        )
        await self._mysql.execute(
            """UPDATE infractions SET active = 0
               WHERE user_id = :user_id AND active = 1 AND type IN (:restrict, :ban)""",
            {
                "user_id": user_id,
                "restrict": _INFRACTION_RESTRICT,
                "ban": _INFRACTION_BAN,
            },
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

        if notes is not None:
            updates.append("notes = :notes")
            params["notes"] = notes

        if updates:
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = :user_id"
            await self._mysql.execute(query, params)

        # Silence lives in infractions (type 2) in the clean schema.
        if silence_end is not None:
            if silence_end > 0:
                await self._mysql.execute(
                    """INSERT INTO infractions (user_id, type, active, expires_at)
                       VALUES (:user_id, :type, :active, FROM_UNIXTIME(:silence_end))""",
                    {
                        "user_id": user_id,
                        "type": _INFRACTION_SILENCE,
                        "active": 1 if silence_end > int(time.time()) else 0,
                        "silence_end": silence_end,
                    },
                )
            else:
                await self._mysql.execute(
                    """UPDATE infractions SET active = 0
                       WHERE user_id = :user_id AND active = 1 AND type = :type""",
                    {"user_id": user_id, "type": _INFRACTION_SILENCE},
                )

    async def wipe_user_stats(
        self,
        user_id: int,
        mode: int | None = None,
        custom_mode: int = 0,
    ) -> None:
        if mode is not None:
            modes = (mode,)
        else:
            modes = _MODES_FOR_CUSTOM.get(custom_mode, (0, 1, 2, 3))

        for m in modes:
            cmode = combined_mode(m, custom_mode)
            await self._mysql.execute(
                f"UPDATE user_stats SET {_WIPE_STATS} WHERE user_id = :user_id AND mode = :cmode",
                {"user_id": user_id, "cmode": cmode},
            )
