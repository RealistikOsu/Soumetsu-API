from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL


class MatchData(BaseModel):
    id: int
    winner_user_id: int | None
    status: str
    name: str
    started_at: datetime
    ended_at: datetime | None


class MatchUserData(BaseModel):
    id: int
    username: str
    country: str
    privileges: int


class MatchPlayerData(MatchUserData):
    match_id: int


class MatchRoundData(BaseModel):
    match_id: int
    round: int
    ruleset_id: int
    started_at: datetime
    ended_at: datetime | None
    beatmap_id: int
    beatmapset_id: int | None
    song_name: str | None
    ranked: int | None
    stars: float | None
    creator: str | None


class MatchScoreData(BaseModel):
    round: int
    user_id: int
    total_score: int
    accuracy: float
    max_combo: int
    rank: str
    passed: bool
    statistics: str


class MatchEventData(BaseModel):
    type: str
    user_id: int | None
    created_at: datetime


def _placeholders(ids: list[int]) -> tuple[str, dict[str, int]]:
    names = ", ".join(f":id_{i}" for i in range(len(ids)))
    return names, {f"id_{i}": value for i, value in enumerate(ids)}


_PLAYER_MATCHES = """SELECT match_id FROM lazer_ranked_play_match_users WHERE user_id = :user_id
               UNION
               SELECT match_id FROM lazer_ranked_play_match_scores WHERE user_id = :user_id
               UNION
               SELECT match_id FROM lazer_ranked_play_match_events
               WHERE user_id = :user_id AND type = 'joined'"""


class RankedPlayRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def find_match(self, match_id: int) -> MatchData | None:
        row = await self._mysql.fetch_one(
            """SELECT id, winner_user_id, status, name, started_at, ended_at
               FROM lazer_ranked_play_matches WHERE id = :match_id""",
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
            f"""SELECT id, winner_user_id, status, name, started_at, ended_at
                FROM lazer_ranked_play_matches
                WHERE status = :status AND id IN ({_PLAYER_MATCHES})
                ORDER BY started_at DESC, id DESC
                {paging}""",
            params,
        )
        return [MatchData(**row) for row in rows]

    async def count_user_matches(self, user_id: int, status: str) -> int:
        count = await self._mysql.fetch_val(
            f"""SELECT COUNT(*) FROM lazer_ranked_play_matches
                WHERE status = :status AND id IN ({_PLAYER_MATCHES})""",
            {"user_id": user_id, "status": status},
        )
        return count or 0

    async def list_players(self, match_ids: list[int]) -> list[MatchPlayerData]:
        if not match_ids:
            return []
        placeholders, params = _placeholders(match_ids)
        rows = await self._mysql.fetch_all(
            f"""SELECT p.match_id, u.id, u.username, u.country, u.privileges
                FROM (
                    SELECT match_id, user_id FROM lazer_ranked_play_match_users
                    WHERE match_id IN ({placeholders})
                    UNION
                    SELECT s.match_id, s.user_id FROM lazer_ranked_play_match_scores s
                    INNER JOIN lazer_ranked_play_matches m ON m.id = s.match_id
                    WHERE m.status = 'active' AND s.match_id IN ({placeholders})
                    UNION
                    SELECT e.match_id, e.user_id FROM lazer_ranked_play_match_events e
                    INNER JOIN lazer_ranked_play_matches m ON m.id = e.match_id
                    WHERE m.status = 'active' AND e.type = 'joined'
                      AND e.user_id IS NOT NULL AND e.match_id IN ({placeholders})
                ) p
                INNER JOIN users u ON u.id = p.user_id AND u.deleted = 0
                ORDER BY p.match_id, u.id""",
            params,
        )
        return [MatchPlayerData(**row) for row in rows]

    async def list_users(self, user_ids: list[int]) -> list[MatchUserData]:
        if not user_ids:
            return []
        placeholders, params = _placeholders(user_ids)
        rows = await self._mysql.fetch_all(
            f"""SELECT id, username, country, privileges
                FROM users WHERE deleted = 0 AND id IN ({placeholders})""",
            params,
        )
        return [MatchUserData(**row) for row in rows]

    async def list_rounds(self, match_ids: list[int]) -> list[MatchRoundData]:
        if not match_ids:
            return []
        placeholders, params = _placeholders(match_ids)
        rows = await self._mysql.fetch_all(
            f"""SELECT r.match_id, r.round, r.ruleset_id, r.started_at, r.ended_at,
                       r.beatmap_id, b.beatmapset_id, b.song_name, b.ranked,
                       CASE r.ruleset_id
                           WHEN 1 THEN b.difficulty_taiko
                           WHEN 2 THEN b.difficulty_ctb
                           WHEN 3 THEN b.difficulty_mania
                           ELSE b.difficulty_std
                       END AS stars,
                       mu.username AS creator
                FROM lazer_ranked_play_match_rounds r
                LEFT JOIN beatmaps b ON b.beatmap_id = r.beatmap_id AND b.ranked != -1
                LEFT JOIN users mu ON mu.id = b.mapper_id
                WHERE r.match_id IN ({placeholders})
                ORDER BY r.match_id, r.round""",
            params,
        )
        return [MatchRoundData(**row) for row in rows]

    async def list_scores(self, match_id: int) -> list[MatchScoreData]:
        rows = await self._mysql.fetch_all(
            """SELECT round, user_id, total_score, accuracy, max_combo,
                      `rank`, passed, statistics
               FROM lazer_ranked_play_match_scores
               WHERE match_id = :match_id
               ORDER BY round, total_score DESC""",
            {"match_id": match_id},
        )
        return [MatchScoreData(**row) for row in rows]

    async def list_events(self, match_id: int) -> list[MatchEventData]:
        rows = await self._mysql.fetch_all(
            """SELECT type, user_id, created_at
               FROM lazer_ranked_play_match_events
               WHERE match_id = :match_id
               ORDER BY created_at, id""",
            {"match_id": match_id},
        )
        return [MatchEventData(**row) for row in rows]
