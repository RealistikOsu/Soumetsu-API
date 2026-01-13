from __future__ import annotations

from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.resources.beatmaps import BeatmapData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError


class BeatmapError(ServiceError):
    BEATMAP_NOT_FOUND = "beatmap_not_found"

    @override
    def service(self) -> str:
        return "beatmaps"

    @override
    def status_code(self) -> int:
        match self:
            case BeatmapError.BEATMAP_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
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
    latest_update: int
    ranked_status_freezed: bool
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
        latest_update=b.latest_update,
        ranked_status_freezed=b.ranked_status_freezed,
        mapper_id=b.mapper_id,
    )


async def get_beatmap(
    ctx: AbstractContext,
    beatmap_id: int,
) -> BeatmapError.OnSuccess[BeatmapResult]:
    beatmap = await ctx.beatmaps.get_by_id(beatmap_id)
    if not beatmap:
        return BeatmapError.BEATMAP_NOT_FOUND

    return _beatmap_to_result(beatmap)


async def get_beatmap_by_md5(
    ctx: AbstractContext,
    beatmap_md5: str,
) -> BeatmapError.OnSuccess[BeatmapResult]:
    beatmap = await ctx.beatmaps.get_by_md5(beatmap_md5)
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

    beatmaps = await ctx.beatmaps.get_popular(mode, limit, offset)
    return [_beatmap_to_result(b) for b in beatmaps]


async def get_beatmapset(
    ctx: AbstractContext,
    beatmapset_id: int,
) -> BeatmapError.OnSuccess[list[BeatmapResult]]:
    beatmaps = await ctx.beatmaps.get_beatmapset(beatmapset_id)
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
        user_id, mode, playstyle, limit, offset
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
