from __future__ import annotations

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
    playstyle: int,
    page: int = 1,
    limit: int = 5,
) -> BeatmapError.OnSuccess[list[MostPlayedResult]]:
    if limit > 50:
        limit = 50
    offset = (page - 1) * limit

    beatmaps = await ctx.beatmaps.get_user_most_played(
        user_id,
        mode,
        playstyle,
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


DAILY_RANK_REQUEST_LIMIT = 2
DAILY_GLOBAL_REQUEST_LIMIT = 50


@dataclass
class RankRequestStatusResult:
    submitted: int
    queue_size: int
    can_submit: bool
    submitted_by_user: int | None = None
    max_per_user: int | None = None
    next_expiration: str | None = None


def _format_relative_time(unix_timestamp: int) -> str:
    import time as time_module

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


import re

BEATMAP_URL_PATTERNS = [
    re.compile(r"osu\.ppy\.sh/beatmapsets/(\d+)(?:#\w+/(\d+))?"),
    re.compile(r"osu\.ppy\.sh/b/(\d+)"),
    re.compile(r"osu\.ppy\.sh/beatmaps/(\d+)"),
    re.compile(r"osu\.ppy\.sh/s/(\d+)"),
    re.compile(r"osu\.ussr\.pl/beatmapsets/(\d+)(?:#\w+/(\d+))?"),
    re.compile(r"osu\.ussr\.pl/b/(\d+)"),
    re.compile(r"osu\.ussr\.pl/beatmaps/(\d+)"),
    re.compile(r"osu\.ussr\.pl/s/(\d+)"),
]


def parse_beatmap_url(url: str) -> tuple[str, int] | None:
    for pattern in BEATMAP_URL_PATTERNS:
        match = pattern.search(url)
        if match:
            groups = match.groups()
            if len(groups) == 2 and groups[1]:
                return ("b", int(groups[1]))
            return ("s", int(groups[0]))
    return None


async def submit_rank_request(
    ctx: AbstractContext,
    user_id: int,
    url: str,
) -> BeatmapError.OnSuccess[int]:
    submitted = await ctx.beatmaps.count_user_rank_requests_today(user_id)
    if submitted >= DAILY_RANK_REQUEST_LIMIT:
        return BeatmapError.DAILY_LIMIT_REACHED

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

    request_id = await ctx.beatmaps.create_rank_request(
        user_id,
        beatmap_id,
        request_type,
    )
    return request_id
