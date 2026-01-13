from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import OptionalAuth
from soumetsu_api.api.v2.context import RequiresAuth
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import beatmaps

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
    updated_at: int
    ranked_status_frozen: bool
    mapper_id: int


class ScorePlayerResponse(BaseModel):
    player_id: int
    username: str
    country: str


class ScoreResponse(BaseModel):
    id: int
    beatmap_md5: str
    player_id: int
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
    submitted_at: int
    play_mode: int
    completed: int
    accuracy: float
    pp: float
    playtime: int
    player: ScorePlayerResponse


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
        updated_at=b.updated_at,
        ranked_status_frozen=b.ranked_status_frozen,
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

    scores_list = await ctx.scores.list_beatmap_scores(
        beatmap.beatmap_md5,
        mode,
        playstyle,
        limit,
        offset,
    )

    return response.create(
        [
            ScoreResponse(
                id=s.id,
                beatmap_md5=s.beatmap_md5,
                player_id=s.player_id,
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
                submitted_at=s.submitted_at,
                play_mode=s.play_mode,
                completed=s.completed,
                accuracy=s.accuracy,
                pp=s.pp,
                playtime=s.playtime,
                player=ScorePlayerResponse(
                    player_id=s.player.player_id,
                    username=s.player.username,
                    country=s.player.country,
                ),
            )
            for s in scores_list
        ],
    )


class RankRequestStatusResponse(BaseModel):
    submitted: int
    queue_size: int
    can_submit: bool
    submitted_by_user: int | None = None
    max_per_user: int | None = None
    next_expiration: str | None = None


class RankRequestSubmitRequest(BaseModel):
    url: str


class RankRequestSubmitResponse(BaseModel):
    request_id: int


@router.get(
    "/rank-requests/status",
    response_model=response.BaseResponse[RankRequestStatusResponse],
)
async def get_rank_request_status(ctx: OptionalAuth) -> Response:
    user_id = ctx.session.user_id if ctx.session else None
    result = await beatmaps.get_rank_request_status(ctx, user_id)
    result = response.unwrap(result)

    return response.create(
        RankRequestStatusResponse(
            submitted=result.submitted,
            queue_size=result.queue_size,
            can_submit=result.can_submit,
            submitted_by_user=result.submitted_by_user,
            max_per_user=result.max_per_user,
            next_expiration=result.next_expiration,
        ),
    )


@router.post(
    "/rank-requests",
    response_model=response.BaseResponse[RankRequestSubmitResponse],
)
async def submit_rank_request(
    ctx: RequiresAuth,
    body: RankRequestSubmitRequest,
) -> Response:
    result = await beatmaps.submit_rank_request(ctx, ctx.session.user_id, body.url)
    result = response.unwrap(result)

    return response.create(RankRequestSubmitResponse(request_id=result))
