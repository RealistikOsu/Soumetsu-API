from __future__ import annotations

import re
import time as time_module
from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.resources.beatmaps import BeatmapData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError


class BeatmapError(ServiceError):
    BEATMAP_NOT_FOUND = "beatmap_not_found"
    ALREADY_REQUESTED = "already_requested"
    DAILY_LIMIT_REACHED = "daily_limit_reached"
    INVALID_URL = "invalid_url"
    ALREADY_RANKED = "already_ranked"

    @override
    def service(self) -> str:
        return "beatmaps"

    @override
    def status_code(self) -> int:
        match self:
            case BeatmapError.BEATMAP_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case BeatmapError.ALREADY_REQUESTED:
                return status.HTTP_409_CONFLICT
            case BeatmapError.DAILY_LIMIT_REACHED:
                return status.HTTP_429_TOO_MANY_REQUESTS
            case BeatmapError.INVALID_URL:
                return status.HTTP_400_BAD_REQUEST
            case BeatmapError.ALREADY_RANKED:
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class BeatmapResult:
    beatmap_id: int
    beatmapset_id: int
    beatmap_md5: str
    song_name: str
    ar: float
    od: float
    mode: int
    difficulty_std: float
    difficulty_taiko: float
    difficulty_ctb: float
    difficulty_mania: float
    max_combo: int
    hit_length: int
    bpm: int
    playcount: int
    passcount: int
    ranked: int
    updated_at: int
    ranked_status_frozen: bool
    mapper_id: int


def _beatmap_to_result(b: BeatmapData) -> BeatmapResult:
    return BeatmapResult(
        beatmap_id=b.beatmap_id,
        beatmapset_id=b.beatmapset_id,
        beatmap_md5=b.beatmap_md5,
        song_name=b.song_name,
        ar=b.ar,
        od=b.od,
        mode=b.mode,
        difficulty_std=b.difficulty_std,
        difficulty_taiko=b.difficulty_taiko,
        difficulty_ctb=b.difficulty_ctb,
        difficulty_mania=b.difficulty_mania,
        max_combo=b.max_combo,
        hit_length=b.hit_length,
        bpm=b.bpm,
        playcount=b.playcount,
        passcount=b.passcount,
        ranked=b.ranked,
        updated_at=b.updated_at,
        ranked_status_frozen=b.ranked_status_frozen,
        mapper_id=b.mapper_id,
    )


async def get_beatmap(
    ctx: AbstractContext,
    beatmap_id: int,
) -> BeatmapError.OnSuccess[BeatmapResult]:
    beatmap = await ctx.beatmaps.find_by_id(beatmap_id)
    if not beatmap:
        return BeatmapError.BEATMAP_NOT_FOUND

    return _beatmap_to_result(beatmap)


async def get_beatmap_by_md5(
    ctx: AbstractContext,
    beatmap_md5: str,
) -> BeatmapError.OnSuccess[BeatmapResult]:
    beatmap = await ctx.beatmaps.find_by_md5(beatmap_md5)
    if not beatmap:
        return BeatmapError.BEATMAP_NOT_FOUND

    return _beatmap_to_result(beatmap)


async def search_beatmaps(
    ctx: AbstractContext,
    query: str | None = None,
    mode: int | None = None,
    status: int | None = None,
    page: int = 1,
    limit: int = 50,
) -> BeatmapError.OnSuccess[list[BeatmapResult]]:
    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    beatmaps = await ctx.beatmaps.search(query, mode, status, limit, offset)
    return [_beatmap_to_result(b) for b in beatmaps]


async def get_popular(
    ctx: AbstractContext,
    mode: int | None = None,
    page: int = 1,
    limit: int = 50,
) -> BeatmapError.OnSuccess[list[BeatmapResult]]:
    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    beatmaps = await ctx.beatmaps.list_popular(mode, limit, offset)
    return [_beatmap_to_result(b) for b in beatmaps]


async def get_beatmapset(
    ctx: AbstractContext,
    beatmapset_id: int,
) -> BeatmapError.OnSuccess[list[BeatmapResult]]:
    beatmaps = await ctx.beatmaps.list_beatmapset(beatmapset_id)
    if not beatmaps:
        return BeatmapError.BEATMAP_NOT_FOUND

    return [_beatmap_to_result(b) for b in beatmaps]


@dataclass
class MostPlayedBeatmapInfo:
    beatmap_id: int
    beatmapset_id: int
    song_name: str


@dataclass
class MostPlayedResult:
    beatmap: MostPlayedBeatmapInfo
    playcount: int


async def get_user_most_played(
    ctx: AbstractContext,
    user_id: int,
    mode: int,
    custom_mode: int,
    page: int = 1,
    limit: int = 5,
) -> BeatmapError.OnSuccess[list[MostPlayedResult]]:
    if limit > 50:
        limit = 50
    offset = (page - 1) * limit

    beatmaps = await ctx.beatmaps.get_user_most_played(
        user_id,
        mode,
        custom_mode,
        limit,
        offset,
    )

    return [
        MostPlayedResult(
            beatmap=MostPlayedBeatmapInfo(
                beatmap_id=b.beatmap_id,
                beatmapset_id=b.beatmapset_id,
                song_name=b.song_name,
            ),
            playcount=b.playcount,
        )
        for b in beatmaps
    ]


DAILY_RANK_REQUEST_LIMIT = 5
DAILY_GLOBAL_REQUEST_LIMIT = 50


@dataclass
class RankRequestBeatmapInfo:
    beatmap_id: int
    beatmapset_id: int
    song_name: str
    ar: float
    od: float
    mode: int
    difficulty_std: float
    difficulty_taiko: float
    difficulty_ctb: float
    difficulty_mania: float
    max_combo: int
    hit_length: int
    bpm: int
    ranked: int
    mapper_id: int


@dataclass
class RankRequestListItem:
    request_id: int
    request_type: str
    requested_at: int
    beatmaps: list[RankRequestBeatmapInfo]


@dataclass
class RankRequestListResult:
    requests: list[RankRequestListItem]
    total: int
    page: int
    limit: int
    has_more: bool


@dataclass
class RankRequestStatusResult:
    submitted: int
    queue_size: int
    can_submit: bool
    submitted_by_user: int | None = None
    max_per_user: int | None = None
    next_expiration: str | None = None


def _format_relative_time(unix_timestamp: int) -> str:
    now = time_module.time()
    tomorrow = unix_timestamp + 86400

    if tomorrow <= now:
        return "now"

    diff = int(tomorrow - now)
    hours = diff // 3600
    minutes = (diff % 3600) // 60

    if hours > 0:
        return f"in {hours}h {minutes}m"
    else:
        return f"in {minutes}m"


async def get_rank_request_status(
    ctx: AbstractContext,
    user_id: int | None = None,
) -> BeatmapError.OnSuccess[RankRequestStatusResult]:
    submitted_today = await ctx.beatmaps.count_rank_requests_today()

    if user_id is None:
        return RankRequestStatusResult(
            submitted=submitted_today,
            queue_size=DAILY_GLOBAL_REQUEST_LIMIT,
            can_submit=False,
        )

    submitted_by_user = await ctx.beatmaps.count_user_rank_requests_today(user_id)
    can_submit = submitted_by_user < DAILY_RANK_REQUEST_LIMIT

    next_expiration = None
    if not can_submit:
        oldest_time = await ctx.beatmaps.find_user_oldest_rank_request_today(user_id)
        if oldest_time:
            next_expiration = _format_relative_time(oldest_time)

    return RankRequestStatusResult(
        submitted=submitted_today,
        queue_size=DAILY_GLOBAL_REQUEST_LIMIT,
        can_submit=can_submit,
        submitted_by_user=submitted_by_user,
        max_per_user=DAILY_RANK_REQUEST_LIMIT,
        next_expiration=next_expiration,
    )


async def check_rank_request(
    ctx: AbstractContext,
    set_id: int,
) -> bool:
    """Check if a beatmapset has already been requested for ranking."""
    existing = await ctx.beatmaps.find_rank_request_by_beatmap(set_id, "s")
    return existing is not None


BEATMAP_URL_PATTERN = re.compile(
    r"(?:/beatmapsets/(\d+)(?:#\w+/(\d+))?)"  # /beatmapsets/{set_id} or /beatmapsets/{set_id}#mode/{beatmap_id}
    r"|(?:/beatmaps/(\d+))"  # /beatmaps/{beatmap_id}
    r"|(?:/b/(\d+))"  # /b/{beatmap_id}
    r"|(?:/s/(\d+))"  # /s/{set_id}
)


def parse_beatmap_url(url: str) -> tuple[str, int] | None:
    """Parse a beatmap URL from any domain.

    Supported formats:
    - /beatmapsets/{set_id} -> ("s", set_id)
    - /beatmapsets/{set_id}#mode/{beatmap_id} -> ("b", beatmap_id)
    - /beatmaps/{beatmap_id} -> ("b", beatmap_id)
    - /b/{beatmap_id} -> ("b", beatmap_id)
    - /s/{set_id} -> ("s", set_id)
    """
    match = BEATMAP_URL_PATTERN.search(url)
    if not match:
        return None

    groups = match.groups()
    # groups: (beatmapset_id, beatmap_from_hash, beatmaps_id, b_id, s_id)

    # /beatmapsets/{set_id}#mode/{beatmap_id}
    if groups[1]:
        return ("b", int(groups[1]))
    # /beatmapsets/{set_id}
    if groups[0]:
        return ("s", int(groups[0]))
    # /beatmaps/{beatmap_id}
    if groups[2]:
        return ("b", int(groups[2]))
    # /b/{beatmap_id}
    if groups[3]:
        return ("b", int(groups[3]))
    # /s/{set_id}
    if groups[4]:
        return ("s", int(groups[4]))

    return None


async def submit_rank_request(
    ctx: AbstractContext,
    user_id: int,
    url: str,
) -> BeatmapError.OnSuccess[int]:
    parsed = parse_beatmap_url(url)
    if not parsed:
        return BeatmapError.INVALID_URL

    request_type, beatmap_id = parsed

    existing = await ctx.beatmaps.find_rank_request_by_beatmap(beatmap_id, request_type)
    if existing:
        return BeatmapError.ALREADY_REQUESTED

    if request_type == "b":
        beatmap = await ctx.beatmaps.find_by_id(beatmap_id)
        if beatmap and beatmap.ranked in (2, 3, 4, 5):
            return BeatmapError.ALREADY_RANKED
    else:
        beatmapset = await ctx.beatmaps.list_beatmapset(beatmap_id)
        if beatmapset and all(b.ranked in (2, 3, 4, 5) for b in beatmapset):
            return BeatmapError.ALREADY_RANKED

    request_id = await ctx.beatmaps.create_rank_request_with_atomic_limit(
        user_id,
        beatmap_id,
        request_type,
        DAILY_RANK_REQUEST_LIMIT,
    )
    if request_id is None:
        return BeatmapError.DAILY_LIMIT_REACHED

    return request_id


async def list_rank_requests(
    ctx: AbstractContext,
    page: int = 1,
    limit: int = 20,
) -> BeatmapError.OnSuccess[RankRequestListResult]:
    if limit > 50:
        limit = 50
    offset = (page - 1) * limit

    rows = await ctx.beatmaps.list_pending_rank_requests(limit + 1, offset)
    total = await ctx.beatmaps.count_pending_rank_requests()

    has_more = len(rows) > limit
    rows = rows[:limit]

    requests_dict: dict[int, RankRequestListItem] = {}
    for row in rows:
        if row.request_id not in requests_dict:
            requests_dict[row.request_id] = RankRequestListItem(
                request_id=row.request_id,
                request_type=row.request_type,
                requested_at=row.requested_at,
                beatmaps=[],
            )
        requests_dict[row.request_id].beatmaps.append(
            RankRequestBeatmapInfo(
                beatmap_id=row.beatmap_id,
                beatmapset_id=row.beatmapset_id,
                song_name=row.song_name,
                ar=row.ar,
                od=row.od,
                mode=row.mode,
                difficulty_std=row.difficulty_std,
                difficulty_taiko=row.difficulty_taiko,
                difficulty_ctb=row.difficulty_ctb,
                difficulty_mania=row.difficulty_mania,
                max_combo=row.max_combo,
                hit_length=row.hit_length,
                bpm=row.bpm,
                ranked=row.ranked,
                mapper_id=row.mapper_id,
            ),
        )

    return RankRequestListResult(
        requests=list(requests_dict.values()),
        total=total,
        page=page,
        limit=limit,
        has_more=has_more,
    )
