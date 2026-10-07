from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated
from typing import Literal

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel
from pydantic import Field

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import OptionalAuth
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.api.v2.ranked_play import BeatmapRefResponse
from soumetsu_api.api.v2.ranked_play import UserRefResponse
from soumetsu_api.services import multiplayer

router = APIRouter()


class MatchSummaryResponse(BaseModel):
    id: int
    name: str
    status: Literal["active", "ended"]
    started_at: datetime
    ended_at: datetime | None
    host: UserRefResponse | None
    map_count: int
    players: list[UserRefResponse]
    star_min: float | None
    star_max: float | None
    cover_set_ids: list[int]


class UserMatchesResponse(BaseModel):
    active: list[MatchSummaryResponse]
    ended: list[MatchSummaryResponse]
    total_ended: int


class ParticipantResponse(BaseModel):
    user: UserRefResponse
    rank: int
    accuracy: float
    play_count: int
    total_score: int


class MapEntryResponse(BaseModel):
    game: int
    mode: int
    mods: int
    beatmap: BeatmapRefResponse


class MatchDetailResponse(BaseModel):
    match: MatchSummaryResponse
    participants: list[ParticipantResponse]
    maps: list[MapEntryResponse]


class ScoreStatisticsResponse(BaseModel):
    count_300: int
    count_100: int
    count_50: int
    count_miss: int
    count_geki: int
    count_katu: int


class GameScoreResponse(BaseModel):
    user: UserRefResponse
    team: int
    score: int
    accuracy: float
    max_combo: int
    passed: bool
    mods: int
    grade: str
    statistics: ScoreStatisticsResponse


class GameDetailResponse(BaseModel):
    number: int
    started_at: datetime
    ended_at: datetime | None
    mode: int
    mods: int
    win_condition: int
    team_type: int
    beatmap: BeatmapRefResponse
    scores: list[GameScoreResponse]


class UserEventResponse(BaseModel):
    type: Literal["joined", "left", "disbanded"]
    at: datetime
    user: UserRefResponse | None


class GameEndedEventResponse(BaseModel):
    type: Literal["game_ended"]
    at: datetime
    user: None
    game: int


class GameEventResponse(BaseModel):
    type: Literal["game"]
    at: datetime
    game: GameDetailResponse


EventResponse = Annotated[
    UserEventResponse | GameEndedEventResponse | GameEventResponse,
    Field(discriminator="type"),
]


class MatchEventsResponse(BaseModel):
    match: MatchSummaryResponse
    events: list[EventResponse]


@router.get(
    "/users/{user_id}/multiplayer/matches",
    response_model=response.BaseResponse[UserMatchesResponse],
)
async def get_user_matches(
    ctx: OptionalAuth,
    user_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
) -> Response:
    result = await multiplayer.get_user_matches(
        ctx,
        user_id,
        page,
        limit,
        viewer=ctx.session,
    )
    result = response.unwrap(result)

    return response.create(UserMatchesResponse.model_validate(asdict(result)))


@router.get(
    "/multiplayer/matches/{match_id}",
    response_model=response.BaseResponse[MatchDetailResponse],
)
async def get_match(ctx: RequiresContext, match_id: int) -> Response:
    result = await multiplayer.get_match(ctx, match_id)
    result = response.unwrap(result)

    return response.create(MatchDetailResponse.model_validate(asdict(result)))


@router.get(
    "/multiplayer/matches/{match_id}/events",
    response_model=response.BaseResponse[MatchEventsResponse],
)
async def get_match_events(ctx: RequiresContext, match_id: int) -> Response:
    result = await multiplayer.get_match_events(ctx, match_id)
    result = response.unwrap(result)

    return response.create(MatchEventsResponse.model_validate(asdict(result)))
