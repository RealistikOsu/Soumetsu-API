from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.constants import CustomMode
from soumetsu_api.constants import GameMode
from soumetsu_api.services import leaderboard

router = APIRouter(prefix="/leaderboard")


class LeaderboardModeStatsResponse(BaseModel):
    pp: int
    accuracy: float
    playcount: int
    level: float


class LeaderboardEntryResponse(BaseModel):
    id: int
    username: str
    country: str
    privileges: int
    chosen_mode: LeaderboardModeStatsResponse
    global_rank: int
    country_rank: int


class FirstPlaceResponse(BaseModel):
    player_id: int
    username: str
    score_id: int
    beatmap_md5: str
    song_name: str
    pp: float
    achieved_at: int
    mode: int


class RankResponse(BaseModel):
    rank: int


class TotalUsersResponse(BaseModel):
    total: int


def _to_response(
    e: leaderboard.LeaderboardEntryResult,
) -> LeaderboardEntryResponse:
    return LeaderboardEntryResponse(
        id=e.id,
        username=e.username,
        country=e.country,
        privileges=e.privileges,
        chosen_mode=LeaderboardModeStatsResponse(
            pp=e.chosen_mode.pp,
            accuracy=e.chosen_mode.accuracy,
            playcount=e.chosen_mode.playcount,
            level=e.chosen_mode.level,
        ),
        global_rank=e.global_rank,
        country_rank=e.country_rank,
    )


def _first_to_response(f: leaderboard.FirstPlaceResult) -> FirstPlaceResponse:
    return FirstPlaceResponse(
        player_id=f.player_id,
        username=f.username,
        score_id=f.score_id,
        beatmap_md5=f.beatmap_md5,
        song_name=f.song_name,
        pp=f.pp,
        achieved_at=f.achieved_at,
        mode=f.mode,
    )


@router.get("/", response_model=response.BaseResponse[list[LeaderboardEntryResponse]])
async def get_global(
    ctx: RequiresContext,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await leaderboard.get_global(ctx, mode, custom_mode, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(e) for e in result])


@router.get(
    "/country/{country}",
    response_model=response.BaseResponse[list[LeaderboardEntryResponse]],
)
async def get_country(
    ctx: RequiresContext,
    country: str,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await leaderboard.get_country(ctx, country, mode, custom_mode, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(e) for e in result])


@router.get("/rank/{user_id}", response_model=response.BaseResponse[RankResponse])
async def get_user_rank(
    ctx: RequiresContext,
    user_id: int,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
) -> Response:
    result = await leaderboard.get_user_rank(ctx, user_id, mode, custom_mode)
    result = response.unwrap(result)

    return response.create(RankResponse(rank=result))


@router.get("/total", response_model=response.BaseResponse[TotalUsersResponse])
async def get_total_ranked_users(
    ctx: RequiresContext,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
) -> Response:
    result = await leaderboard.get_total_ranked_users(ctx, mode, custom_mode)
    result = response.unwrap(result)

    return response.create(TotalUsersResponse(total=result))


@router.get(
    "/firsts/oldest",
    response_model=response.BaseResponse[list[FirstPlaceResponse]],
)
async def list_oldest_firsts(
    ctx: RequiresContext,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await leaderboard.list_oldest_firsts(ctx, mode, custom_mode, page, limit)
    result = response.unwrap(result)

    return response.create([_first_to_response(f) for f in result])
