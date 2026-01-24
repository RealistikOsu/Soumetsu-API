from __future__ import annotations

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.constants import get_mode_suffix
from soumetsu_api.constants import get_stats_table
from soumetsu_api.resources.scores import SCORE_TABLES

CLAN_PERM_MEMBER = 1
CLAN_PERM_OWNER = 2


class ClanData(BaseModel):
    id: int
    name: str
    description: str
    icon: str
    tag: str
    member_limit: int


class ClanMemberData(BaseModel):
    user_id: int
    username: str
    country: str
    perms: int


class ClanMemberStats(BaseModel):
    pp: int
    ranked_score: int
    total_score: int
    playcount: int
    replays_watched: int
    total_hits: int


class ClanTopScore(BaseModel):
    id: int
    player_id: int
    username: str
    score: int
    max_combo: int
    full_combo: bool
    mods: int
    accuracy: float
    pp: float
    beatmap_id: int
    beatmapset_id: int
    song_name: str
    difficulty: float
    ranked: int


class ClanMemberLeaderboardEntry(BaseModel):
    id: int
    username: str
    country: str
    pp: int
    accuracy: float
    playcount: int
    total_score: int


class ClansRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def get_by_id(self, clan_id: int) -> ClanData | None:
        row = await self._mysql.fetch_one(
            """SELECT id, name, description, icon, tag, mlimit as member_limit
               FROM clans WHERE id = :clan_id""",
            {"clan_id": clan_id},
        )
        if not row:
            return None

        return ClanData(**row)

    async def get_by_tag(self, tag: str) -> ClanData | None:
        row = await self._mysql.fetch_one(
            """SELECT id, name, description, icon, tag, mlimit as member_limit
               FROM clans WHERE tag = :tag""",
            {"tag": tag},
        )
        if not row:
            return None

        return ClanData(**row)

    async def search(
        self,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ClanData]:
        if query:
            rows = await self._mysql.fetch_all(
                """SELECT id, name, description, icon, tag, mlimit as member_limit
                   FROM clans WHERE name LIKE :query
                   ORDER BY id DESC
                   LIMIT :limit OFFSET :offset""",
                {"query": f"%{query}%", "limit": limit, "offset": offset},
            )
        else:
            rows = await self._mysql.fetch_all(
                """SELECT id, name, description, icon, tag, mlimit as member_limit
                   FROM clans
                   ORDER BY id DESC
                   LIMIT :limit OFFSET :offset""",
                {"limit": limit, "offset": offset},
            )

        return [ClanData(**row) for row in rows]

    async def create(
        self,
        name: str,
        description: str,
        tag: str,
        icon: str = "",
    ) -> int:
        return await self._mysql.execute(
            """INSERT INTO clans (name, description, icon, tag)
               VALUES (:name, :description, :icon, :tag)""",
            {"name": name, "description": description, "icon": icon, "tag": tag},
        )

    async def update(
        self,
        clan_id: int,
        name: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> None:
        updates = []
        params: dict[str, int | str] = {"clan_id": clan_id}

        if name is not None:
            updates.append("name = :name")
            params["name"] = name

        if description is not None:
            updates.append("description = :description")
            params["description"] = description

        if icon is not None:
            updates.append("icon = :icon")
            params["icon"] = icon

        if not updates:
            return

        query = f"UPDATE clans SET {', '.join(updates)} WHERE id = :clan_id"
        await self._mysql.execute(query, params)

    async def delete(self, clan_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM user_clans WHERE clan = :clan_id",
            {"clan_id": clan_id},
        )
        await self._mysql.execute(
            "DELETE FROM clans_invites WHERE clan = :clan_id",
            {"clan_id": clan_id},
        )
        await self._mysql.execute(
            "DELETE FROM clans WHERE id = :clan_id",
            {"clan_id": clan_id},
        )

    async def get_members(
        self,
        clan_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ClanMemberData]:
        rows = await self._mysql.fetch_all(
            """SELECT uc.user as user_id, u.username, u.country, uc.perms
               FROM user_clans uc
               INNER JOIN users u ON uc.user = u.id
               WHERE uc.clan = :clan_id
               ORDER BY uc.perms DESC, u.username ASC
               LIMIT :limit OFFSET :offset""",
            {"clan_id": clan_id, "limit": limit, "offset": offset},
        )
        return [ClanMemberData(**row) for row in rows]

    async def get_member_count(self, clan_id: int) -> int:
        result = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM user_clans WHERE clan = :clan_id",
            {"clan_id": clan_id},
        )
        return result or 0

    async def get_user_clan(self, user_id: int) -> int | None:
        result = await self._mysql.fetch_val(
            "SELECT clan FROM user_clans WHERE user = :user_id",
            {"user_id": user_id},
        )
        return result

    async def get_user_perms(self, user_id: int, clan_id: int) -> int | None:
        result = await self._mysql.fetch_val(
            "SELECT perms FROM user_clans WHERE user = :user_id AND clan = :clan_id",
            {"user_id": user_id, "clan_id": clan_id},
        )
        return result

    async def add_member(
        self,
        clan_id: int,
        user_id: int,
        perms: int = CLAN_PERM_MEMBER,
    ) -> None:
        await self._mysql.execute(
            """INSERT INTO user_clans (user, clan, perms)
               VALUES (:user_id, :clan_id, :perms)""",
            {"user_id": user_id, "clan_id": clan_id, "perms": perms},
        )

    async def add_member_with_atomic_limit(
        self,
        clan_id: int,
        user_id: int,
        limit: int,
        perms: int = CLAN_PERM_MEMBER,
    ) -> bool:
        """Atomically add a member only if the clan is below the limit.

        Returns True if the member was added, False if the clan was full.
        """
        result = await self._mysql.execute(
            """INSERT INTO user_clans (user, clan, perms)
               SELECT :user_id, :clan_id, :perms
               FROM dual
               WHERE (SELECT COUNT(*) FROM user_clans WHERE clan = :clan_id) < :limit""",
            {
                "user_id": user_id,
                "clan_id": clan_id,
                "perms": perms,
                "limit": limit,
            },
        )
        return result > 0

    async def remove_member(self, clan_id: int, user_id: int) -> None:
        await self._mysql.execute(
            "DELETE FROM user_clans WHERE user = :user_id AND clan = :clan_id",
            {"user_id": user_id, "clan_id": clan_id},
        )

    async def name_exists(self, name: str) -> bool:
        count = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM clans WHERE name = :name",
            {"name": name},
        )
        return count > 0

    async def tag_exists(self, tag: str) -> bool:
        count = await self._mysql.fetch_val(
            "SELECT COUNT(*) FROM clans WHERE tag = :tag",
            {"tag": tag},
        )
        return count > 0

    async def get_invite(self, clan_id: int) -> str | None:
        result = await self._mysql.fetch_val(
            "SELECT invite FROM clans_invites WHERE clan = :clan_id",
            {"clan_id": clan_id},
        )
        return result

    async def set_invite(self, clan_id: int, invite: str) -> None:
        await self._mysql.execute(
            """INSERT INTO clans_invites (clan, invite)
               VALUES (:clan_id, :invite)
               ON DUPLICATE KEY UPDATE invite = :invite""",
            {"clan_id": clan_id, "invite": invite},
        )

    async def get_clan_by_invite(self, invite: str) -> int | None:
        result = await self._mysql.fetch_val(
            "SELECT clan FROM clans_invites WHERE invite = :invite",
            {"invite": invite},
        )
        return result

    async def get_clan_member_stats(
        self,
        clan_id: int,
        mode: int,
        custom_mode: int,
    ) -> list[ClanMemberStats]:
        table = get_stats_table(custom_mode)
        suffix = get_mode_suffix(mode)

        query = f"""
            SELECT s.pp_{suffix} as pp,
                   s.ranked_score_{suffix} as ranked_score,
                   s.total_score_{suffix} as total_score,
                   s.playcount_{suffix} as playcount,
                   s.replays_watched_{suffix} as replays_watched,
                   s.total_hits_{suffix} as total_hits
            FROM user_clans uc
            INNER JOIN {table} s ON uc.user = s.id
            INNER JOIN users u ON uc.user = u.id
            WHERE uc.clan = :clan_id
            AND u.privileges & 1 > 0
            ORDER BY s.pp_{suffix} DESC
        """
        rows = await self._mysql.fetch_all(query, {"clan_id": clan_id})
        return [ClanMemberStats(**row) for row in rows]

    async def get_all_clan_ids(self) -> list[int]:
        rows = await self._mysql.fetch_all(
            "SELECT id FROM clans ORDER BY id",
            {},
        )
        return [row["id"] for row in rows]

    async def get_clan_top_scores(
        self,
        clan_id: int,
        mode: int,
        custom_mode: int,
        limit: int = 4,
    ) -> list[ClanTopScore]:
        table = SCORE_TABLES[custom_mode]
        diff_col = [
            "difficulty_std",
            "difficulty_taiko",
            "difficulty_ctb",
            "difficulty_mania",
        ][mode]

        query = f"""
            SELECT s.id, s.userid as player_id, s.score, s.max_combo,
                   s.full_combo, s.mods, s.accuracy, s.pp,
                   b.beatmap_id, b.beatmapset_id, b.song_name,
                   b.{diff_col} as difficulty, b.ranked,
                   u.username
            FROM {table} s
            INNER JOIN user_clans uc ON s.userid = uc.user
            INNER JOIN beatmaps b ON s.beatmap_md5 = b.beatmap_md5
            INNER JOIN users u ON s.userid = u.id
            WHERE uc.clan = :clan_id
            AND s.play_mode = :mode
            AND s.completed = 3
            AND s.pp > 0
            AND b.ranked = 2
            AND u.privileges & 1 > 0
            ORDER BY s.pp DESC
            LIMIT :limit
        """
        rows = await self._mysql.fetch_all(
            query,
            {"clan_id": clan_id, "mode": mode, "limit": limit},
        )
        return [ClanTopScore(**row) for row in rows]

    async def get_clan_member_leaderboard(
        self,
        clan_id: int,
        mode: int,
        custom_mode: int,
    ) -> list[ClanMemberLeaderboardEntry]:
        table = get_stats_table(custom_mode)
        suffix = get_mode_suffix(mode)

        query = f"""
            SELECT s.id, u.username, u.country,
                   s.pp_{suffix} as pp,
                   s.avg_accuracy_{suffix} as accuracy,
                   s.playcount_{suffix} as playcount,
                   s.total_score_{suffix} as total_score
            FROM user_clans uc
            INNER JOIN {table} s ON uc.user = s.id
            INNER JOIN users u ON uc.user = u.id
            WHERE uc.clan = :clan_id
            AND u.privileges & 1 > 0
            ORDER BY s.pp_{suffix} DESC
        """
        rows = await self._mysql.fetch_all(query, {"clan_id": clan_id})
        return [ClanMemberLeaderboardEntry(**row) for row in rows]
