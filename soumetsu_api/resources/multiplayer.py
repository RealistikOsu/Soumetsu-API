from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.resources.ranked_play import MatchPlayerData
from soumetsu_api.resources.ranked_play import RoundBeatmapData
from soumetsu_api.resources.ranked_play import id_placeholders
from soumetsu_api.resources.ranked_play import stars_for


class MatchData(BaseModel):
    id: int
    name: str
    host_id: int | None
    status: str
    created_at: datetime
    ended_at: datetime | None


class GameData(RoundBeatmapData):
    match_id: int
    game: int
    mods: int
    win_condition: int
    team_type: int
    started_at: datetime
    ended_at: datetime | None


class GameScoreData(BaseModel):
    game: int
    user_id: int
    team: int
    score: int
    accuracy: float
    max_combo: int
    count_300: int
    count_100: int
    count_50: int
    count_miss: int
    count_geki: int
    count_katu: int
    mods: int
    passed: bool


class MatchEventData(BaseModel):
    type: str
    user_id: int | None
    created_at: datetime


_PLAYER_MATCHES = """SELECT match_id FROM mp_match_events
                     WHERE user_id = :user_id AND type IN ('joined', 'left')
                     UNION
                     SELECT match_id FROM mp_match_scores WHERE user_id = :user_id"""


class MultiplayerRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def find_match(self, match_id: int) -> MatchData | None:
        row = await self._mysql.fetch_one(
            """SELECT id, name, host_id, status, created_at, ended_at
               FROM mp_matches WHERE id = :match_id""",
            {"match_id": match_id},
        )
        return MatchData(**row) if row else None

    async def list_user_matches(
        self,
        user_id: int,
        status: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[MatchData]:
        paging = "LIMIT :limit OFFSET :offset" if limit is not None else ""
        params: dict[str, int | str] = {"user_id": user_id, "status": status}
        if limit is not None:
            params |= {"limit": limit, "offset": offset}
        rows = await self._mysql.fetch_all(
            f"""SELECT m.id, m.name, m.host_id, m.status, m.created_at, m.ended_at
                FROM ({_PLAYER_MATCHES}) p
                INNER JOIN mp_matches m ON m.id = p.match_id
                WHERE m.status = :status
                ORDER BY m.id DESC
                {paging}""",
            params,
        )
        return [MatchData(**row) for row in rows]

    async def count_user_matches(self, user_id: int, status: str) -> int:
        count = await self._mysql.fetch_val(
            f"""SELECT COUNT(*)
                FROM ({_PLAYER_MATCHES}) p
                INNER JOIN mp_matches m ON m.id = p.match_id
                WHERE m.status = :status""",
            {"user_id": user_id, "status": status},
        )
        return count or 0

    async def list_players(self, match_ids: list[int]) -> list[MatchPlayerData]:
        if not match_ids:
            return []
        placeholders, params = id_placeholders(match_ids)
        rows = await self._mysql.fetch_all(
            f"""SELECT p.match_id, u.id, u.username, u.country, u.privileges
                FROM (
                    SELECT match_id, user_id FROM mp_match_events
                    WHERE type IN ('joined', 'left') AND user_id IS NOT NULL
                      AND match_id IN ({placeholders})
                    UNION
                    SELECT match_id, user_id FROM mp_match_scores
                    WHERE match_id IN ({placeholders})
                ) p
                INNER JOIN users u ON u.id = p.user_id AND u.deleted = 0
                ORDER BY p.match_id, u.id""",
            params,
        )
        return [MatchPlayerData(**row) for row in rows]

    async def list_games(self, match_ids: list[int]) -> list[GameData]:
        if not match_ids:
            return []
        placeholders, params = id_placeholders(match_ids)
        rows = await self._mysql.fetch_all(
            f"""SELECT g.match_id, g.game, g.mode AS ruleset_id, g.mods,
                       g.win_condition, g.team_type, g.started_at, g.ended_at,
                       g.beatmap_id, b.beatmapset_id, b.song_name, b.ranked,
                       {stars_for("g.mode")} AS stars,
                       mu.username AS creator
                FROM mp_match_games g
                LEFT JOIN beatmaps b ON b.beatmap_id = g.beatmap_id AND b.ranked != -1
                LEFT JOIN users mu ON mu.id = b.mapper_id
                WHERE g.match_id IN ({placeholders})
                ORDER BY g.match_id, g.game""",
            params,
        )
        return [GameData(**row) for row in rows]

    async def list_scores(self, match_id: int) -> list[GameScoreData]:
        rows = await self._mysql.fetch_all(
            """SELECT game, user_id, team, score, accuracy, max_combo,
                      count_300, count_100, count_50, count_miss,
                      count_geki, count_katu, mods, passed
               FROM mp_match_scores
               WHERE match_id = :match_id
               ORDER BY game, score DESC""",
            {"match_id": match_id},
        )
        return [GameScoreData(**row) for row in rows]

    async def list_events(self, match_id: int) -> list[MatchEventData]:
        rows = await self._mysql.fetch_all(
            """SELECT type, user_id, created_at
               FROM mp_match_events
               WHERE match_id = :match_id
               ORDER BY id""",
            {"match_id": match_id},
        )
        return [MatchEventData(**row) for row in rows]
