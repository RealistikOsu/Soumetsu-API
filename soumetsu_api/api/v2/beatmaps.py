from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import beatmaps
from soumetsu_api.services import scores as scores_svc


router = APIRouter(prefix="/beatmaps")


class BeatmapResponse(BaseModel):
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


class ScoreResponse(BaseModel):
    id: int
    beatmap_md5: str
    user_id: int
    score: int
    max_combo: int
    full_combo: bool
    mods: int
    count_300: int
    count_100: int
    count_50: int
    count_katus: int
    count_gekis: int
    count_misses: int
    time: str
    play_mode: int
    completed: int
    accuracy: float
    pp: float
    playtime: int


def _to_response(b: beatmaps.BeatmapResult) -> BeatmapResponse:
    return BeatmapResponse(
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


@router.get("/", response_model=response.BaseResponse[list[BeatmapResponse]])
async def search_beatmaps(
    ctx: RequiresContext,
    q: str | None = Query(None),
    mode: int | None = Query(None, ge=0, le=3),
    status: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await beatmaps.search_beatmaps(ctx, q, mode, status, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(b) for b in result])


@router.get("/popular", response_model=response.BaseResponse[list[BeatmapResponse]])
async def get_popular(
    ctx: RequiresContext,
    mode: int | None = Query(None, ge=0, le=3),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await beatmaps.get_popular(ctx, mode, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(b) for b in result])


@router.get("/lookup", response_model=response.BaseResponse[BeatmapResponse])
async def lookup_beatmap(
    ctx: RequiresContext,
    md5: str = Query(..., min_length=32, max_length=32),
) -> Response:
    result = await beatmaps.get_beatmap_by_md5(ctx, md5)
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.get(
    "/set/{beatmapset_id}",
    response_model=response.BaseResponse[list[BeatmapResponse]],
)
async def get_beatmapset(
    ctx: RequiresContext,
    beatmapset_id: int,
) -> Response:
    result = await beatmaps.get_beatmapset(ctx, beatmapset_id)
    result = response.unwrap(result)

    return response.create([_to_response(b) for b in result])


@router.get("/{beatmap_id}", response_model=response.BaseResponse[BeatmapResponse])
async def get_beatmap(
    ctx: RequiresContext,
    beatmap_id: int,
) -> Response:
    result = await beatmaps.get_beatmap(ctx, beatmap_id)
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.get(
    "/{beatmap_id}/scores",
    response_model=response.BaseResponse[list[ScoreResponse]],
)
async def get_beatmap_scores(
    ctx: RequiresContext,
    beatmap_id: int,
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    beatmap = await beatmaps.get_beatmap(ctx, beatmap_id)
    beatmap = response.unwrap(beatmap)

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    scores = await ctx.scores.get_beatmap_scores(
        beatmap.beatmap_md5, mode, playstyle, limit, offset
    )

    return response.create(
        [
            ScoreResponse(
                id=s.id,
                beatmap_md5=s.beatmap_md5,
                user_id=s.user_id,
                score=s.score,
                max_combo=s.max_combo,
                full_combo=s.full_combo,
                mods=s.mods,
                count_300=s.count_300,
                count_100=s.count_100,
                count_50=s.count_50,
                count_katus=s.count_katus,
                count_gekis=s.count_gekis,
                count_misses=s.count_misses,
                time=s.time,
                play_mode=s.play_mode,
                completed=s.completed,
                accuracy=s.accuracy,
                pp=s.pp,
                playtime=s.playtime,
            )
            for s in scores
        ]
    )
