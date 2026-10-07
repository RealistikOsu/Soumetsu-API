from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import override

from fastapi import status

from soumetsu_api.resources.rooms import BestScoreData
from soumetsu_api.resources.rooms import LadderData
from soumetsu_api.resources.rooms import PercentileData
from soumetsu_api.resources.rooms import RoomData
from soumetsu_api.resources.rooms import RoomItemData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.services.ranked_play import BeatmapRef
from soumetsu_api.services.ranked_play import UserRef
from soumetsu_api.services.ranked_play import as_utc
from soumetsu_api.services.ranked_play import beatmap_ref
from soumetsu_api.services.ranked_play import is_visible
from soumetsu_api.services.ranked_play import user_ref


class RoomsError(ServiceError):
    DAILY_CHALLENGE_NOT_FOUND = "daily_challenge_not_found"
    ROOM_NOT_FOUND = "room_not_found"
    ITEM_NOT_FOUND = "item_not_found"

    @override
    def service(self) -> str:
        return "rooms"

    @override
    def status_code(self) -> int:
        match self:
            case (
                RoomsError.DAILY_CHALLENGE_NOT_FOUND
                | RoomsError.ROOM_NOT_FOUND
                | RoomsError.ITEM_NOT_FOUND
            ):
                return status.HTTP_404_NOT_FOUND
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class Mod:
    acronym: str
    settings: dict[str, object]


@dataclass
class ChallengeDay:
    date: date
    has_challenge: bool


@dataclass
class ChallengeDaysResult:
    days: list[ChallengeDay]


@dataclass
class DailyChallengeResult:
    date: date
    beatmap: BeatmapRef
    ruleset: int
    required_mods: list[Mod]
    participants: int
    top_10_score: int | None
    top_50_score: int | None
    room_id: int | None


@dataclass
class DailyScore:
    rank: int
    user: UserRef
    total_score: int
    accuracy: float
    max_combo: int
    play_count: int
    grade: str
    mods: list[Mod]


@dataclass
class ScoresResult:
    total: int
    scores: list[DailyScore]


@dataclass
class PlaylistSummary:
    id: int
    name: str
    host: UserRef | None
    created_at: datetime
    ends_at: datetime | None
    ended_at: datetime | None
    item_count: int
    participants: int
    first_beatmap: BeatmapRef | None
    star_min: float | None
    star_max: float | None


@dataclass
class PlaylistsResult:
    total: int
    rooms: list[PlaylistSummary]


@dataclass
class PlaylistItem:
    item_id: int
    ruleset: int
    beatmap: BeatmapRef
    required_mods: list[Mod]
    allowed_mods: list[Mod]
    expired: bool
    participants: int


@dataclass
class PlaylistDetailResult:
    room: PlaylistSummary
    items: list[PlaylistItem]


def parse_mods(raw: str | list | None) -> list[Mod]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []

    return [
        Mod(
            acronym=mod["acronym"],
            settings=mod["settings"] if isinstance(mod.get("settings"), dict) else {},
        )
        for mod in raw
        if isinstance(mod, dict) and isinstance(mod.get("acronym"), str)
    ]


def month_bounds(year: int, month: int) -> tuple[date, date]:
    end = date(year + month // 12, month % 12 + 1, 1)
    return date(year, month, 1), end


def pick_percentiles(
    rows: list[PercentileData],
) -> tuple[int, int | None, int | None]:
    if not rows:
        return 0, None, None

    n = rows[0].n
    by_position = {row.rn: row.best for row in rows}
    return n, by_position.get((n + 9) // 10), by_position.get((n + 1) // 2)


def shape_scores(
    ladder: list[LadderData],
    bests: list[BestScoreData],
    offset: int,
) -> list[DailyScore]:
    best_by_user: dict[int, BestScoreData] = {}
    for score in bests:
        best_by_user.setdefault(score.user_id, score)

    return [
        DailyScore(
            rank=offset + position,
            user=UserRef(id=row.user_id, username=row.username, country=row.country),
            total_score=row.best,
            accuracy=round(best_by_user[row.user_id].accuracy * 100, 2),
            max_combo=best_by_user[row.user_id].max_combo,
            play_count=row.plays,
            grade=best_by_user[row.user_id].rank,
            mods=parse_mods(best_by_user[row.user_id].mods),
        )
        for position, row in enumerate(ladder, start=1)
        if row.user_id in best_by_user
    ]


def build_summary(
    room: RoomData,
    host: UserRef | None,
    items: list[RoomItemData],
    participants: int,
) -> PlaylistSummary:
    stars = [i.stars for i in items if i.stars and i.stars > 0]
    return PlaylistSummary(
        id=room.id,
        name=room.name,
        host=host,
        created_at=as_utc(room.created_at),
        ends_at=as_utc(room.ends_at) if room.ends_at else None,
        ended_at=as_utc(room.ended_at) if room.ended_at else None,
        item_count=len(items),
        participants=participants,
        first_beatmap=beatmap_ref(items[0]) if items else None,
        star_min=min(stars, default=None),
        star_max=max(stars, default=None),
    )


async def _hosts(ctx: AbstractContext, rooms: list[RoomData]) -> dict[int, UserRef]:
    host_ids = sorted({r.host_id for r in rooms if r.host_id is not None})
    users = await ctx.ranked_play.list_users(host_ids)
    return {u.id: user_ref(u) for u in users if is_visible(u)}


async def _summaries(
    ctx: AbstractContext,
    rooms: list[RoomData],
    items: list[RoomItemData],
) -> list[PlaylistSummary]:
    ids = [r.id for r in rooms]
    counts = {
        c.room_id: c.participants for c in await ctx.rooms.count_room_participants(ids)
    }
    hosts = await _hosts(ctx, rooms)

    return [
        build_summary(
            room,
            hosts.get(room.host_id) if room.host_id is not None else None,
            [i for i in items if i.room_id == room.id],
            counts.get(room.id, 0),
        )
        for room in rooms
    ]


async def _scores(
    ctx: AbstractContext,
    room_id: int,
    item_id: int,
    page: int,
    limit: int,
) -> ScoresResult:
    offset = (page - 1) * limit
    total = await ctx.rooms.count_ladder(room_id, item_id)
    ladder = await ctx.rooms.list_ladder(room_id, item_id, limit, offset)
    bests = await ctx.rooms.list_best_scores(
        room_id,
        item_id,
        {row.user_id: row.best for row in ladder},
    )
    return ScoresResult(total=total, scores=shape_scores(ladder, bests, offset))


async def get_challenge_days(
    ctx: AbstractContext,
    year: int,
    month: int,
) -> ChallengeDaysResult:
    start, end = month_bounds(year, month)
    days = await ctx.rooms.list_scheduled_days(start, end)
    return ChallengeDaysResult(
        days=[ChallengeDay(date=day, has_challenge=True) for day in days],
    )


async def get_daily_challenge(
    ctx: AbstractContext,
    day: date,
) -> RoomsError.OnSuccess[DailyChallengeResult]:
    room = await ctx.rooms.find_daily_room(day)
    items = await ctx.rooms.list_items([room.id]) if room else []

    if room and items:
        item = items[0]
        participants, top_10, top_50 = pick_percentiles(
            await ctx.rooms.list_percentiles(room.id, item.item_id),
        )
        return DailyChallengeResult(
            date=day,
            beatmap=beatmap_ref(item),
            ruleset=item.ruleset_id,
            required_mods=parse_mods(item.required_mods),
            participants=participants,
            top_10_score=top_10,
            top_50_score=top_50,
            room_id=room.id,
        )

    scheduled = await ctx.rooms.find_scheduled_beatmap(day)
    if not scheduled:
        return RoomsError.DAILY_CHALLENGE_NOT_FOUND

    return DailyChallengeResult(
        date=day,
        beatmap=beatmap_ref(scheduled),
        ruleset=scheduled.ruleset_id,
        required_mods=[],
        participants=0,
        top_10_score=None,
        top_50_score=None,
        room_id=room.id if room else None,
    )


async def get_daily_scores(
    ctx: AbstractContext,
    day: date,
    page: int,
    limit: int,
) -> RoomsError.OnSuccess[ScoresResult]:
    room = await ctx.rooms.find_daily_room(day)
    items = await ctx.rooms.list_items([room.id]) if room else []
    if room and items:
        return await _scores(ctx, room.id, items[0].item_id, page, limit)

    if not await ctx.rooms.find_scheduled_beatmap(day):
        return RoomsError.DAILY_CHALLENGE_NOT_FOUND
    return ScoresResult(total=0, scores=[])


async def get_playlists(
    ctx: AbstractContext,
    room_status: str,
    page: int,
    limit: int,
) -> PlaylistsResult:
    rooms = await ctx.rooms.list_rooms(room_status, limit, (page - 1) * limit)
    total = await ctx.rooms.count_rooms(room_status)
    items = await ctx.rooms.list_items([r.id for r in rooms])
    return PlaylistsResult(total=total, rooms=await _summaries(ctx, rooms, items))


async def get_playlist(
    ctx: AbstractContext,
    room_id: int,
) -> RoomsError.OnSuccess[PlaylistDetailResult]:
    room = await ctx.rooms.find_room(room_id)
    if not room:
        return RoomsError.ROOM_NOT_FOUND

    items = await ctx.rooms.list_items([room.id])
    counts: dict[int | None, int] = {
        c.room_item_id: c.participants
        for c in await ctx.rooms.count_item_participants(room.id)
    }
    [summary] = await _summaries(ctx, [room], items)

    return PlaylistDetailResult(
        room=summary,
        items=[
            PlaylistItem(
                item_id=item.item_id,
                ruleset=item.ruleset_id,
                beatmap=beatmap_ref(item),
                required_mods=parse_mods(item.required_mods),
                allowed_mods=parse_mods(item.allowed_mods),
                expired=item.expired,
                participants=counts.get(item.item_id, 0),
            )
            for item in items
        ],
    )


async def get_playlist_item_scores(
    ctx: AbstractContext,
    room_id: int,
    item_id: int,
    page: int,
    limit: int,
) -> RoomsError.OnSuccess[ScoresResult]:
    if not await ctx.rooms.find_room(room_id):
        return RoomsError.ROOM_NOT_FOUND

    items = await ctx.rooms.list_items([room_id])
    if all(item.item_id != item_id for item in items):
        return RoomsError.ITEM_NOT_FOUND

    return await _scores(ctx, room_id, item_id, page, limit)
