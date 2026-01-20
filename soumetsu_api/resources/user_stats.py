from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.constants import get_mode_suffix
from soumetsu_api.constants import get_stats_table


class UserStatsData(BaseModel):
    pp: int
    accuracy: float
    playcount: int
    total_score: int
    ranked_score: int
    total_hits: int
    playtime: int
    max_combo: int
    replays_watched: int
    level: int


class UserSettingsData(BaseModel):
    username_aka: str
    favourite_mode: int
    prefer_relax: int
    play_style: int
    show_country: bool


class UserStatsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    def _get_table(self, custom_mode: int) -> str:
        return get_stats_table(custom_mode)

    def _get_mode_suffix(self, mode: int) -> str:
        return get_mode_suffix(mode)

    async def initialise_all(self, user_id: int, username: str) -> None:
        await self._mysql.execute(
            """INSERT INTO users_stats (id, username) VALUES (:id, :username)""",
            {"id": user_id, "username": username},
        )

        await self._mysql.execute(
            """INSERT INTO rx_stats (id, username) VALUES (:id, :username)""",
            {"id": user_id, "username": username},
        )

        await self._mysql.execute(
            """INSERT INTO ap_stats (id, username) VALUES (:id, :username)""",
            {"id": user_id, "username": username},
        )

    async def get_stats(
        self,
        user_id: int,
        mode: int,
        custom_mode: int,
    ) -> UserStatsData | None:
        table = self._get_table(custom_mode)
        suffix = self._get_mode_suffix(mode)

        query = f"""
            SELECT
                pp_{suffix} as pp,
                avg_accuracy_{suffix} as accuracy,
                playcount_{suffix} as playcount,
                total_score_{suffix} as total_score,
                ranked_score_{suffix} as ranked_score,
                total_hits_{suffix} as total_hits,
                playtime_{suffix} as playtime,
                max_combo_{suffix} as max_combo,
                replays_watched_{suffix} as replays_watched,
                level_{suffix} as level
            FROM {table}
            WHERE id = :user_id
        """
        row = await self._mysql.fetch_one(query, {"user_id": user_id})
        if not row:
            return None

        return UserStatsData(
            pp=row["pp"],
            accuracy=row["accuracy"],
            playcount=row["playcount"],
            total_score=row["total_score"],
            ranked_score=row["ranked_score"],
            total_hits=row["total_hits"],
            playtime=row["playtime"],
            max_combo=row["max_combo"],
            replays_watched=row["replays_watched"],
            level=row["level"],
        )

    async def get_first_place_count(
        self,
        user_id: int,
        mode: int,
        custom_mode: int,
    ) -> int:
        query = """
            SELECT COUNT(*) FROM first_places
            WHERE user_id = :user_id
            AND mode = :mode
            AND relax = :relax
        """
        result = await self._mysql.fetch_val(
            query,
            {"user_id": user_id, "mode": mode, "relax": custom_mode},
        )
        return result or 0

    async def get_settings(self, user_id: int) -> UserSettingsData | None:
        row = await self._mysql.fetch_one(
            """SELECT username_aka, favourite_mode, prefer_relax,
                      play_style, show_country
               FROM users_stats WHERE id = :user_id""",
            {"user_id": user_id},
        )
        if not row:
            return None

        return UserSettingsData(
            username_aka=row["username_aka"],
            favourite_mode=row["favourite_mode"],
            prefer_relax=row["prefer_relax"],
            play_style=row["play_style"],
            show_country=bool(row["show_country"]),
        )

    async def update_settings(
        self,
        user_id: int,
        username_aka: str | None = None,
        favourite_mode: int | None = None,
        prefer_relax: int | None = None,
        play_style: int | None = None,
        show_country: bool | None = None,
    ) -> None:
        updates = []
        params: dict[str, int | str | bool] = {"user_id": user_id}

        if username_aka is not None:
            updates.append("username_aka = :username_aka")
            params["username_aka"] = username_aka

        if favourite_mode is not None:
            updates.append("favourite_mode = :favourite_mode")
            params["favourite_mode"] = favourite_mode

        if prefer_relax is not None:
            updates.append("prefer_relax = :prefer_relax")
            params["prefer_relax"] = prefer_relax

        if play_style is not None:
            updates.append("play_style = :play_style")
            params["play_style"] = play_style

        if show_country is not None:
            updates.append("show_country = :show_country")
            params["show_country"] = int(show_country)

        if not updates:
            return

        query = f"UPDATE users_stats SET {', '.join(updates)} WHERE id = :user_id"
        await self._mysql.execute(query, params)

    async def get_userpage(self, user_id: int) -> str | None:
        result = await self._mysql.fetch_val(
            "SELECT userpage_content FROM users_stats WHERE id = :user_id",
            {"user_id": user_id},
        )
        return result

    async def update_userpage(self, user_id: int, content: str) -> None:
        await self._mysql.execute(
            "UPDATE users_stats SET userpage_content = :content WHERE id = :user_id",
            {"user_id": user_id, "content": content},
        )
