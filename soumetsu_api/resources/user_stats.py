from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.constants import combined_mode


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
    custom_badge_icon: str
    custom_badge_name: str
    show_custom_badge: bool
    can_custom_badge: bool


class PreferredModeStats(BaseModel):
    mode: int
    custom_mode: int
    pp: int
    accuracy: float
    playcount: int


def _decompose_mode(cmode: int) -> tuple[int, int]:
    """Clean-schema combined mode 0-7 -> (mode, custom_mode)."""
    if cmode == 7:
        return 0, 2  # autopilot std
    if cmode >= 4:
        return cmode - 4, 1  # relax std/taiko/ctb
    return cmode, 0  # vanilla std/taiko/ctb/mania


class UserStatsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def get_stats(
        self,
        user_id: int,
        mode: int,
        custom_mode: int,
    ) -> UserStatsData | None:
        cmode = combined_mode(mode, custom_mode)
        query = """
            SELECT pp, accuracy, playcount, total_score, ranked_score,
                   total_hits, playtime, max_combo, replays_watched, level
            FROM user_stats
            WHERE user_id = :user_id AND mode = :cmode
        """
        row = await self._mysql.fetch_one(query, {"user_id": user_id, "cmode": cmode})
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
        cmode = combined_mode(mode, custom_mode)
        query = """
            SELECT COUNT(*) FROM first_places
            WHERE user_id = :user_id
            AND mode = :cmode
        """
        result = await self._mysql.fetch_val(
            query,
            {"user_id": user_id, "cmode": cmode},
        )
        return result or 0

    async def get_settings(self, user_id: int) -> UserSettingsData | None:
        row = await self._mysql.fetch_one(
            """SELECT username_aka, favourite_mode, prefer_relax,
                      play_style, show_country, custom_badge_icon,
                      custom_badge_name, show_custom_badge, can_custom_badge
               FROM user_settings WHERE user_id = :user_id""",
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
            custom_badge_icon=row["custom_badge_icon"] or "",
            custom_badge_name=row["custom_badge_name"] or "",
            show_custom_badge=bool(row["show_custom_badge"]),
            can_custom_badge=bool(row["can_custom_badge"]),
        )

    async def update_settings(
        self,
        user_id: int,
        username_aka: str | None = None,
        favourite_mode: int | None = None,
        prefer_relax: int | None = None,
        play_style: int | None = None,
        show_country: bool | None = None,
        custom_badge_icon: str | None = None,
        custom_badge_name: str | None = None,
        show_custom_badge: bool | None = None,
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

        if custom_badge_icon is not None:
            updates.append("custom_badge_icon = :custom_badge_icon")
            params["custom_badge_icon"] = custom_badge_icon

        if custom_badge_name is not None:
            updates.append("custom_badge_name = :custom_badge_name")
            params["custom_badge_name"] = custom_badge_name

        if show_custom_badge is not None:
            updates.append("show_custom_badge = :show_custom_badge")
            params["show_custom_badge"] = int(show_custom_badge)

        if not updates:
            return

        query = f"UPDATE user_settings SET {', '.join(updates)} WHERE user_id = :user_id"
        await self._mysql.execute(query, params)

    async def get_userpage(self, user_id: int) -> str | None:
        result = await self._mysql.fetch_val(
            "SELECT userpage_content FROM user_settings WHERE user_id = :user_id",
            {"user_id": user_id},
        )
        return result

    async def update_userpage(self, user_id: int, content: str) -> None:
        await self._mysql.execute(
            "UPDATE user_settings SET userpage_content = :content WHERE user_id = :user_id",
            {"user_id": user_id, "content": content},
        )

    async def get_preferred_mode_stats(self, user_id: int) -> PreferredModeStats | None:
        """Pick the mode (0-7) with the highest playcount from tall user_stats."""
        rows = await self._mysql.fetch_all(
            """SELECT mode, pp, accuracy, playcount
               FROM user_stats WHERE user_id = :user_id""",
            {"user_id": user_id},
        )
        if not rows:
            return None

        best = max(rows, key=lambda r: r["playcount"] or 0)
        mode, custom_mode = _decompose_mode(best["mode"])

        return PreferredModeStats(
            mode=mode,
            custom_mode=custom_mode,
            pp=best["pp"] or 0,
            accuracy=best["accuracy"] or 0.0,
            playcount=best["playcount"] or 0,
        )
