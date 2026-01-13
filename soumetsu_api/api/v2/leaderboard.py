from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import leaderboard


router = APIRouter(prefix="/leaderboard")


class LeaderboardEntryResponse(BaseModel):
    user_id: int
    username: str
    country: str
    pp: int
    accuracy: float
    playcount: int
    rank: int


class FirstPlaceResponse(BaseModel):
    user_id: int
    username: str
    score_id: int
    beatmap_md5: str
    song_name: str
    pp: float
    timestamp: int
    mode: int


class RankResponse(BaseModel):
    rank: int


def _to_response(
    e: leaderboard.LeaderboardEntryResult,
) -> LeaderboardEntryResponse:
    return LeaderboardEntryResponse(
        user_id=e.user_id,
        username=e.username,
        country=e.country,
        pp=e.pp,
        accuracy=e.accuracy,
        playcount=e.playcount,
        rank=e.rank,
    )


def _first_to_response(f: leaderboard.FirstPlaceResult) -> FirstPlaceResponse:
    return FirstPlaceResponse(
        user_id=f.user_id,
        username=f.username,
        score_id=f.score_id,
        beatmap_md5=f.beatmap_md5,
        song_name=f.song_name,
        pp=f.pp,
        timestamp=f.timestamp,
        mode=f.mode,
    )


@router.get("/", response_model=response.BaseResponse[list[LeaderboardEntryResponse]])
async def get_global(
    ctx: RequiresContext,
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await leaderboard.get_global(ctx, mode, playstyle, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(e) for e in result])


@router.get(
    "/country/{country}",
    response_model=response.BaseResponse[list[LeaderboardEntryResponse]],
)
async def get_country(
    ctx: RequiresContext,
    country: str,
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await leaderboard.get_country(ctx, country, mode, playstyle, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(e) for e in result])


@router.get("/rank", response_model=response.BaseResponse[RankResponse])
async def get_rank_for_pp(
    ctx: RequiresContext,
    pp: int = Query(..., ge=0),
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
) -> Response:
    result = await leaderboard.get_rank_for_pp(ctx, pp, mode, playstyle)
    result = response.unwrap(result)

    return response.create(RankResponse(rank=result))


@router.get(
    "/firsts/oldest",
    response_model=response.BaseResponse[list[FirstPlaceResponse]],
)
async def get_oldest_firsts(
    ctx: RequiresContext,
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await leaderboard.get_oldest_firsts(ctx, mode, playstyle, page, limit)
    result = response.unwrap(result)

    return response.create([_first_to_response(f) for f in result])
