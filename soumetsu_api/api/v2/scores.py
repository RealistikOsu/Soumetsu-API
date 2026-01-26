from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresAuthTransaction
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.constants import CustomMode
from soumetsu_api.constants import GameMode
from soumetsu_api.services import scores

router = APIRouter()


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


class BeatmapInfo(BaseModel):
    beatmap_id: int
    beatmapset_id: int
    song_name: str
    difficulty: float
    ranked: int


class ScoreWithBeatmapResponse(ScoreResponse):
    beatmap: BeatmapInfo


class ScoreTopPlayResponse(ScoreWithBeatmapResponse):
    username: str


class ScoreTopPlayMixedResponse(ScoreTopPlayResponse):
    custom_mode: int


@router.get(
    "/scores/top",
    response_model=response.BaseResponse[list[ScoreTopPlayResponse]],
)
async def get_top_plays(
    ctx: RequiresContext,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await scores.get_top_plays(ctx, mode, custom_mode, page, limit)
    result = response.unwrap(result)

    return response.create(
        [
            ScoreTopPlayResponse(
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
                beatmap=BeatmapInfo(
                    beatmap_id=s.beatmap_id,
                    beatmapset_id=s.beatmapset_id,
                    song_name=s.song_name,
                    difficulty=s.difficulty,
                    ranked=s.ranked,
                ),
                username=s.username,
            )
            for s in result
        ],
    )


@router.get(
    "/scores/top/mixed",
    response_model=response.BaseResponse[list[ScoreTopPlayMixedResponse]],
)
async def get_top_plays_mixed(ctx: RequiresContext) -> Response:
    result = await scores.get_top_plays_all_modes(ctx)

    return response.create(
        [
            ScoreTopPlayMixedResponse(
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
                beatmap=BeatmapInfo(
                    beatmap_id=s.beatmap_id,
                    beatmapset_id=s.beatmapset_id,
                    song_name=s.song_name,
                    difficulty=s.difficulty,
                    ranked=s.ranked,
                ),
                username=s.username,
                custom_mode=s.custom_mode,
            )
            for s in result
        ],
    )


@router.get("/scores/{score_id}", response_model=response.BaseResponse[ScoreResponse])
async def get_score(
    ctx: RequiresContext,
    score_id: int,
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
) -> Response:
    result = await scores.get_score(ctx, score_id, custom_mode)
    result = response.unwrap(result)

    return response.create(
        ScoreResponse(
            id=result.id,
            beatmap_md5=result.beatmap_md5,
            player_id=result.player_id,
            score=result.score,
            max_combo=result.max_combo,
            full_combo=result.full_combo,
            mods=result.mods,
            count_300=result.count_300,
            count_100=result.count_100,
            count_50=result.count_50,
            count_katus=result.count_katus,
            count_gekis=result.count_gekis,
            count_misses=result.count_misses,
            submitted_at=result.submitted_at,
            play_mode=result.play_mode,
            completed=result.completed,
            accuracy=result.accuracy,
            pp=result.pp,
            playtime=result.playtime,
        ),
    )


@router.post("/scores/{score_id}/pin", response_model=response.BaseResponse[None])
async def pin_score(
    ctx: RequiresAuthTransaction,
    score_id: int,
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
) -> Response:
    result = await scores.pin_score(ctx, ctx.user_id, score_id, custom_mode)
    response.unwrap(result)

    return response.create(None)


@router.delete("/scores/{score_id}/pin", response_model=response.BaseResponse[None])
async def unpin_score(
    ctx: RequiresAuthTransaction,
    score_id: int,
) -> Response:
    result = await scores.unpin_score(ctx, ctx.user_id, score_id)
    response.unwrap(result)

    return response.create(None)


def _to_response(s: scores.ScoreWithBeatmapResult) -> ScoreWithBeatmapResponse:
    return ScoreWithBeatmapResponse(
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
        beatmap=BeatmapInfo(
            beatmap_id=s.beatmap_id,
            beatmapset_id=s.beatmapset_id,
            song_name=s.song_name,
            difficulty=s.difficulty,
            ranked=s.ranked,
        ),
    )


@router.get(
    "/users/{user_id}/scores/best",
    response_model=response.BaseResponse[list[ScoreWithBeatmapResponse]],
)
async def get_player_best(
    ctx: RequiresContext,
    user_id: int,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await scores.get_player_best(ctx, user_id, mode, custom_mode, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(s) for s in result])


@router.get(
    "/users/{user_id}/scores/recent",
    response_model=response.BaseResponse[list[ScoreWithBeatmapResponse]],
)
async def get_player_recent(
    ctx: RequiresContext,
    user_id: int,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await scores.get_player_recent(
        ctx,
        user_id,
        mode,
        custom_mode,
        page,
        limit,
    )
    result = response.unwrap(result)

    return response.create([_to_response(s) for s in result])


@router.get(
    "/users/{user_id}/scores/firsts",
    response_model=response.BaseResponse[list[ScoreWithBeatmapResponse]],
)
async def get_player_firsts(
    ctx: RequiresContext,
    user_id: int,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await scores.get_player_firsts(
        ctx,
        user_id,
        mode,
        custom_mode,
        page,
        limit,
    )
    result = response.unwrap(result)

    return response.create([_to_response(s) for s in result])


@router.get(
    "/users/{user_id}/scores/pinned",
    response_model=response.BaseResponse[list[ScoreWithBeatmapResponse]],
)
async def get_player_pinned(
    ctx: RequiresContext,
    user_id: int,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await scores.get_player_pinned(
        ctx,
        user_id,
        mode,
        custom_mode,
        page,
        limit,
    )
    result = response.unwrap(result)

    return response.create([_to_response(s) for s in result])
