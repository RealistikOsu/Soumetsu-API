from __future__ import annotations

from dataclasses import asdict
from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.api.v2.ranked_play import BeatmapRefResponse
from soumetsu_api.api.v2.ranked_play import UserRefResponse
from soumetsu_api.services import rooms

daily_router = APIRouter(prefix="/daily-challenge")
playlist_router = APIRouter(prefix="/playlists")


class ModResponse(BaseModel):
    acronym: str
    settings: dict[str, object]


class ChallengeDayResponse(BaseModel):
    date: date
    has_challenge: bool


class ChallengeDaysResponse(BaseModel):
    days: list[ChallengeDayResponse]


class DailyChallengeResponse(BaseModel):
    date: date
    starts_at: datetime
    ends_at: datetime
    freemod: bool
    beatmap: BeatmapRefResponse
    ruleset: int
    required_mods: list[ModResponse]
    participants: int
    stable_participants: int
    stable_top_10_score: int | None
    stable_top_50_score: int | None
    top_10_score: int | None
    top_50_score: int | None
    room_id: int | None
    theme: str | None = None


class DailyScoreResponse(BaseModel):
    rank: int
    user: UserRefResponse
    total_score: int
    accuracy: float
    max_combo: int
    play_count: int
    grade: str
    mods: list[ModResponse]


class ScoresResponse(BaseModel):
    total: int
    scores: list[DailyScoreResponse]


class PlaylistSummaryResponse(BaseModel):
    id: int
    name: str
    host: UserRefResponse | None
    created_at: datetime
    ends_at: datetime | None
    ended_at: datetime | None
    item_count: int
    participants: int
    first_beatmap: BeatmapRefResponse | None
    star_min: float | None
    star_max: float | None


class PlaylistsResponse(BaseModel):
    total: int
    rooms: list[PlaylistSummaryResponse]


class PlaylistItemResponse(BaseModel):
    item_id: int
    ruleset: int
    beatmap: BeatmapRefResponse
    required_mods: list[ModResponse]
    allowed_mods: list[ModResponse]
    expired: bool
    participants: int


class PlaylistDetailResponse(BaseModel):
    room: PlaylistSummaryResponse
    items: list[PlaylistItemResponse]


@daily_router.get(
    "/days",
    response_model=response.BaseResponse[ChallengeDaysResponse],
)
async def get_days(
    ctx: RequiresContext,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> Response:
    result = await rooms.get_challenge_days(ctx, year, month)

    return response.create(ChallengeDaysResponse.model_validate(asdict(result)))


@daily_router.get(
    "/{day}",
    response_model=response.BaseResponse[DailyChallengeResponse],
)
async def get_daily_challenge(ctx: RequiresContext, day: date) -> Response:
    result = await rooms.get_daily_challenge(ctx, day)
    result = response.unwrap(result)

    return response.create(DailyChallengeResponse.model_validate(asdict(result)))


@daily_router.get(
    "/{day}/scores",
    response_model=response.BaseResponse[ScoresResponse],
)
async def get_daily_scores(
    ctx: RequiresContext,
    day: date,
    source: Literal["lazer", "stable"] = "lazer",
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await rooms.get_daily_scores(ctx, day, page, limit, source)
    result = response.unwrap(result)

    return response.create(ScoresResponse.model_validate(asdict(result)))


@playlist_router.get(
    "",
    response_model=response.BaseResponse[PlaylistsResponse],
)
async def get_playlists(
    ctx: RequiresContext,
    status: Literal["active", "ended"] = "active",
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
) -> Response:
    result = await rooms.get_playlists(ctx, status, page, limit)

    return response.create(PlaylistsResponse.model_validate(asdict(result)))


@playlist_router.get(
    "/{room_id}",
    response_model=response.BaseResponse[PlaylistDetailResponse],
)
async def get_playlist(ctx: RequiresContext, room_id: int) -> Response:
    result = await rooms.get_playlist(ctx, room_id)
    result = response.unwrap(result)

    return response.create(PlaylistDetailResponse.model_validate(asdict(result)))


@playlist_router.get(
    "/{room_id}/items/{item_id}/scores",
    response_model=response.BaseResponse[ScoresResponse],
)
async def get_playlist_item_scores(
    ctx: RequiresContext,
    room_id: int,
    item_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await rooms.get_playlist_item_scores(ctx, room_id, item_id, page, limit)
    result = response.unwrap(result)

    return response.create(ScoresResponse.model_validate(asdict(result)))
