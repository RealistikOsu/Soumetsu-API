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
                      play_style, show_country, custom_badge_icon,
                      custom_badge_name, show_custom_badge, can_custom_badge
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

    async def get_preferred_mode_stats(self, user_id: int) -> PreferredModeStats | None:
        """Find the mode combination with highest playcount using a single query."""
        query = """
            SELECT
                vn.playcount_std as vn_std_pc, vn.playcount_taiko as vn_taiko_pc,
                vn.playcount_ctb as vn_ctb_pc, vn.playcount_mania as vn_mania_pc,
                vn.pp_std as vn_std_pp, vn.pp_taiko as vn_taiko_pp,
                vn.pp_ctb as vn_ctb_pp, vn.pp_mania as vn_mania_pp,
                vn.avg_accuracy_std as vn_std_acc, vn.avg_accuracy_taiko as vn_taiko_acc,
                vn.avg_accuracy_ctb as vn_ctb_acc, vn.avg_accuracy_mania as vn_mania_acc,

                rx.playcount_std as rx_std_pc, rx.playcount_taiko as rx_taiko_pc,
                rx.playcount_ctb as rx_ctb_pc,
                rx.pp_std as rx_std_pp, rx.pp_taiko as rx_taiko_pp,
                rx.pp_ctb as rx_ctb_pp,
                rx.avg_accuracy_std as rx_std_acc, rx.avg_accuracy_taiko as rx_taiko_acc,
                rx.avg_accuracy_ctb as rx_ctb_acc,

                ap.playcount_std as ap_std_pc,
                ap.pp_std as ap_std_pp,
                ap.avg_accuracy_std as ap_std_acc
            FROM users_stats vn
            LEFT JOIN rx_stats rx ON vn.id = rx.id
            LEFT JOIN ap_stats ap ON vn.id = ap.id
            WHERE vn.id = :user_id
        """
        row = await self._mysql.fetch_one(query, {"user_id": user_id})
        if not row:
            return None

        # All 8 valid mode combinations: (custom_mode, mode, pc_key, pp_key, acc_key)
        combinations = [
            (0, 0, "vn_std_pc", "vn_std_pp", "vn_std_acc"),
            (0, 1, "vn_taiko_pc", "vn_taiko_pp", "vn_taiko_acc"),
            (0, 2, "vn_ctb_pc", "vn_ctb_pp", "vn_ctb_acc"),
            (0, 3, "vn_mania_pc", "vn_mania_pp", "vn_mania_acc"),
            (1, 0, "rx_std_pc", "rx_std_pp", "rx_std_acc"),
            (1, 1, "rx_taiko_pc", "rx_taiko_pp", "rx_taiko_acc"),
            (1, 2, "rx_ctb_pc", "rx_ctb_pp", "rx_ctb_acc"),
            (2, 0, "ap_std_pc", "ap_std_pp", "ap_std_acc"),
        ]

        best = (0, 0, 0, 0.0, 0)  # (custom_mode, mode, pp, acc, playcount)
        for cm, m, pc_key, pp_key, acc_key in combinations:
            pc = row[pc_key] or 0
            if pc > best[4]:
                best = (cm, m, row[pp_key] or 0, row[acc_key] or 0.0, pc)

        return PreferredModeStats(
            custom_mode=best[0],
            mode=best[1],
            pp=best[2],
            accuracy=best[3],
            playcount=best[4],
        )
