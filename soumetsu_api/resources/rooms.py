from __future__ import annotations

from datetime import date
from datetime import datetime

from pydantic import BaseModel

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.resources.ranked_play import RoundBeatmapData
from soumetsu_api.resources.ranked_play import id_placeholders
from soumetsu_api.resources.ranked_play import stars_for

STATUS_FILTERS = {
    "active": "ended_at IS NULL",
    "ended": "ended_at IS NOT NULL",
}

_LADDER = """(SELECT user_id, MAX(total_score) AS best, COUNT(*) AS plays
              FROM lazer_scores
              WHERE room_id = :room_id AND room_item_id = :item_id
              GROUP BY user_id) g
             INNER JOIN users u ON u.id = g.user_id AND u.privileges & 1"""


def _beatmap_columns(ruleset: str) -> str:
    return f"""b.beatmapset_id, b.song_name, b.ranked,
                       {stars_for(ruleset)} AS stars,
                       mu.username AS creator"""


def _beatmap_joins(beatmap: str) -> str:
    return f"""LEFT JOIN beatmaps b ON b.beatmap_id = {beatmap} AND b.ranked != -1
                LEFT JOIN users mu ON mu.id = b.mapper_id"""


class RoomData(BaseModel):
    id: int
    name: str
    host_id: int | None
    challenge_date: date | None
    created_at: datetime
    ends_at: datetime | None
    ended_at: datetime | None


class RoomItemData(RoundBeatmapData):
    room_id: int
    item_id: int
    required_mods: str
    allowed_mods: str
    expired: bool


class LadderData(BaseModel):
    user_id: int
    username: str
    country: str
    best: int
    plays: int


class BestScoreData(BaseModel):
    user_id: int
    total_score: int
    accuracy: float
    max_combo: int
    rank: str
    mods: str | list | None
    created_at: datetime


class StableLadderData(BaseModel):
    user_id: int
    username: str
    country: str
    score: int
    accuracy: float
    max_combo: int
    mods: int
    playback_rate: float
    count_300: int
    count_100: int
    count_50: int
    count_katus: int
    count_gekis: int
    count_misses: int
    plays: int


class PercentileData(BaseModel):
    n: int
    rn: int
    best: int


class CountData(BaseModel):
    room_id: int
    room_item_id: int | None = None
    participants: int


# "+ 0" on completed and play_mode keeps MySQL on the beatmap_md5 index instead of intersecting low-cardinality ones.
# The daily challenge is no-mod, so stable plays with any mod bit set don't count.
_STABLE_PASSED = """FROM scores s
             INNER JOIN users u ON u.id = s.userid AND u.privileges & 1
             WHERE s.beatmap_md5 = :md5 AND s.play_mode + 0 = :mode AND s.mods = 0
               AND s.time >= :start AND s.time < :end AND s.completed + 0 >= 1"""


class RoomsRepository:
    __slots__ = ("_mysql",)

    def __init__(self, mysql: ImplementsMySQL) -> None:
        self._mysql = mysql

    async def list_scheduled_days(self, start: date, end: date) -> list[date]:
        rows = await self._mysql.fetch_all(
            """SELECT challenge_date FROM lazer_daily_challenges
               WHERE challenge_date >= :start AND challenge_date < :end
               ORDER BY challenge_date""",
            {"start": start, "end": end},
        )
        return [row["challenge_date"] for row in rows]

    async def find_scheduled_beatmap(self, day: date) -> RoundBeatmapData | None:
        row = await self._mysql.fetch_one(
            f"""SELECT d.beatmap_id, COALESCE(b.mode, 0) AS ruleset_id,
                       {_beatmap_columns("b.mode")}
                FROM lazer_daily_challenges d
                {_beatmap_joins("d.beatmap_id")}
                WHERE d.challenge_date = :day""",
            {"day": day},
        )
        return RoundBeatmapData(**row) if row else None

    async def find_room(self, room_id: int) -> RoomData | None:
        row = await self._mysql.fetch_one(
            """SELECT id, name, host_id, challenge_date, created_at, ends_at, ended_at
               FROM lazer_rooms WHERE id = :room_id AND category = 'normal'""",
            {"room_id": room_id},
        )
        return RoomData(**row) if row else None

    async def find_daily_room(self, day: date) -> RoomData | None:
        row = await self._mysql.fetch_one(
            """SELECT id, name, host_id, challenge_date, created_at, ends_at, ended_at
               FROM lazer_rooms
               WHERE challenge_date = :day AND category = 'daily_challenge'""",
            {"day": day},
        )
        return RoomData(**row) if row else None

    async def list_rooms(
        self,
        status: str,
        limit: int,
        offset: int,
    ) -> list[RoomData]:
        rows = await self._mysql.fetch_all(
            f"""SELECT id, name, host_id, challenge_date, created_at, ends_at, ended_at
                FROM lazer_rooms
                WHERE category = 'normal' AND {STATUS_FILTERS[status]}
                ORDER BY id DESC
                LIMIT :limit OFFSET :offset""",
            {"limit": limit, "offset": offset},
        )
        return [RoomData(**row) for row in rows]

    async def count_rooms(self, status: str) -> int:
        count = await self._mysql.fetch_val(
            f"""SELECT COUNT(*) FROM lazer_rooms
                WHERE category = 'normal' AND {STATUS_FILTERS[status]}""",
        )
        return count or 0

    async def list_items(self, room_ids: list[int]) -> list[RoomItemData]:
        if not room_ids:
            return []
        names, params = id_placeholders(room_ids)
        rows = await self._mysql.fetch_all(
            f"""SELECT i.room_id, i.item_id, i.beatmap_id, i.ruleset_id,
                       i.required_mods, i.allowed_mods, i.expired,
                       {_beatmap_columns("i.ruleset_id")}
                FROM lazer_room_items i
                {_beatmap_joins("i.beatmap_id")}
                WHERE i.room_id IN ({names})
                ORDER BY i.room_id, i.item_id""",
            params,
        )
        return [RoomItemData(**row) for row in rows]

    async def count_room_participants(self, room_ids: list[int]) -> list[CountData]:
        if not room_ids:
            return []
        names, params = id_placeholders(room_ids)
        rows = await self._mysql.fetch_all(
            f"""SELECT g.room_id, COUNT(*) AS participants
                FROM (SELECT room_id, user_id FROM lazer_scores
                      WHERE room_id IN ({names})
                      GROUP BY room_id, user_id) g
                INNER JOIN users u ON u.id = g.user_id AND u.privileges & 1
                GROUP BY g.room_id""",
            params,
        )
        return [CountData(**row) for row in rows]

    async def count_item_participants(self, room_id: int) -> list[CountData]:
        rows = await self._mysql.fetch_all(
            """SELECT g.room_id, g.room_item_id, COUNT(*) AS participants
               FROM (SELECT room_id, room_item_id, user_id FROM lazer_scores
                     WHERE room_id = :room_id
                     GROUP BY room_id, room_item_id, user_id) g
               INNER JOIN users u ON u.id = g.user_id AND u.privileges & 1
               GROUP BY g.room_id, g.room_item_id""",
            {"room_id": room_id},
        )
        return [CountData(**row) for row in rows]

    async def list_percentiles(
        self, room_id: int, item_id: int
    ) -> list[PercentileData]:
        rows = await self._mysql.fetch_all(
            f"""SELECT r.n, r.rn, r.best
                FROM (SELECT g.best,
                             ROW_NUMBER() OVER (ORDER BY g.best DESC, g.user_id) AS rn,
                             COUNT(*) OVER () AS n
                      FROM {_LADDER}) r
                WHERE r.rn IN (CEIL(r.n / 10), CEIL(r.n / 2))""",
            {"room_id": room_id, "item_id": item_id},
        )
        return [PercentileData(**row) for row in rows]

    async def count_ladder(self, room_id: int, item_id: int) -> int:
        count = await self._mysql.fetch_val(
            f"SELECT COUNT(*) FROM {_LADDER}",
            {"room_id": room_id, "item_id": item_id},
        )
        return count or 0

    async def list_ladder(
        self,
        room_id: int,
        item_id: int,
        limit: int,
        offset: int,
    ) -> list[LadderData]:
        rows = await self._mysql.fetch_all(
            f"""SELECT g.user_id, u.username, u.country, g.best, g.plays
                FROM {_LADDER}
                ORDER BY g.best DESC, g.user_id
                LIMIT :limit OFFSET :offset""",
            {
                "room_id": room_id,
                "item_id": item_id,
                "limit": limit,
                "offset": offset,
            },
        )
        return [LadderData(**row) for row in rows]

    async def list_best_scores(
        self,
        room_id: int,
        item_id: int,
        bests: dict[int, int],
    ) -> list[BestScoreData]:
        if not bests:
            return []
        pairs = ", ".join(f"(:user_{i}, :score_{i})" for i in range(len(bests)))
        params: dict[str, int] = {"room_id": room_id, "item_id": item_id}
        for i, (user_id, score) in enumerate(bests.items()):
            params[f"user_{i}"] = user_id
            params[f"score_{i}"] = score
        rows = await self._mysql.fetch_all(
            f"""SELECT user_id, total_score, accuracy, max_combo, `rank`, mods, created_at
                FROM lazer_scores
                WHERE room_id = :room_id AND room_item_id = :item_id
                  AND (user_id, total_score) IN ({pairs})
                ORDER BY created_at""",
            params,
        )
        return [BestScoreData(**row) for row in rows]

    async def find_beatmap_md5(self, beatmap_id: int) -> str | None:
        return await self._mysql.fetch_val(
            "SELECT beatmap_md5 FROM beatmaps WHERE beatmap_id = :beatmap_id LIMIT 1",
            {"beatmap_id": beatmap_id},
        )

    async def count_stable_players(
        self,
        md5: str,
        mode: int,
        start: int,
        end: int,
    ) -> int:
        count = await self._mysql.fetch_val(
            f"SELECT COUNT(DISTINCT s.userid) {_STABLE_PASSED}",
            {"md5": md5, "mode": mode, "start": start, "end": end},
        )
        return count or 0

    async def list_stable_percentiles(
        self,
        md5: str,
        mode: int,
        start: int,
        end: int,
    ) -> list[PercentileData]:
        rows = await self._mysql.fetch_all(
            f"""SELECT r.n, r.rn, r.best
                FROM (SELECT g.best,
                             ROW_NUMBER() OVER (ORDER BY g.best DESC, g.userid) AS rn,
                             COUNT(*) OVER () AS n
                      FROM (SELECT s.userid, MAX(s.score) AS best {_STABLE_PASSED}
                            GROUP BY s.userid) g) r
                WHERE r.rn IN (CEIL(r.n / 10), CEIL(r.n / 2))""",
            {"md5": md5, "mode": mode, "start": start, "end": end},
        )
        return [PercentileData(**row) for row in rows]

    async def list_stable_ladder(
        self,
        md5: str,
        mode: int,
        start: int,
        end: int,
        limit: int,
        offset: int,
    ) -> list[StableLadderData]:
        rows = await self._mysql.fetch_all(
            """SELECT r.userid AS user_id, u.username, u.country, r.score, r.accuracy,
                      r.max_combo, r.mods, r.playback_rate,
                      r.`300_count` AS count_300, r.`100_count` AS count_100,
                      r.`50_count` AS count_50, r.katus_count AS count_katus,
                      r.gekis_count AS count_gekis, r.misses_count AS count_misses,
                      r.plays
               FROM (SELECT s.userid, s.score, s.accuracy, s.max_combo, s.mods,
                            s.playback_rate, s.`300_count`, s.`100_count`, s.`50_count`,
                            s.katus_count, s.gekis_count, s.misses_count, s.time,
                            s.completed,
                            ROW_NUMBER() OVER (
                                PARTITION BY s.userid
                                ORDER BY (s.completed + 0 >= 1) DESC, s.score DESC,
                                         s.time, s.id
                            ) AS rn,
                            COUNT(*) OVER (PARTITION BY s.userid) AS plays
                     FROM scores s
                     WHERE s.beatmap_md5 = :md5 AND s.play_mode + 0 = :mode
                       AND s.mods = 0
                       AND s.time >= :start AND s.time < :end) r
               INNER JOIN users u ON u.id = r.userid AND u.privileges & 1
               WHERE r.rn = 1 AND r.completed + 0 >= 1
               ORDER BY r.score DESC, r.time, r.userid
               LIMIT :limit OFFSET :offset""",
            {
                "md5": md5,
                "mode": mode,
                "start": start,
                "end": end,
                "limit": limit,
                "offset": offset,
            },
        )
        return [StableLadderData(**row) for row in rows]
