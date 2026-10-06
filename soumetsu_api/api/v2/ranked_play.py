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
from soumetsu_api.services import ranked_play

router = APIRouter()


class UserRefResponse(BaseModel):
    id: int
    username: str
    country: str


class BeatmapRefResponse(BaseModel):
    id: int
    set_id: int
    artist: str
    title: str
    version: str
    creator: str
    ranked_status: int
    star_rating: float | None
    mode: int


class MatchSummaryResponse(BaseModel):
    id: int
    name: str
    status: Literal["active", "ended"]
    started_at: datetime
    ended_at: datetime | None
    winner_id: int | None
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
    round: int
    ruleset: int
    beatmap: BeatmapRefResponse


class MatchDetailResponse(BaseModel):
    match: MatchSummaryResponse
    participants: list[ParticipantResponse]
    maps: list[MapEntryResponse]


class RoundScoreResponse(BaseModel):
    user: UserRefResponse
    total_score: int
    accuracy: float
    max_combo: int
    rank: str
    passed: bool
    statistics: dict[str, int]


class RoundDetailResponse(BaseModel):
    number: int
    started_at: datetime
    ended_at: datetime | None
    ruleset: int
    beatmap: BeatmapRefResponse
    scores: list[RoundScoreResponse]


class UserEventResponse(BaseModel):
    type: Literal["joined", "left", "disbanded"]
    at: datetime
    user: UserRefResponse | None


class RoundEndedEventResponse(BaseModel):
    type: Literal["round_ended"]
    at: datetime
    user: None
    round: int


class RoundEventResponse(BaseModel):
    type: Literal["round"]
    at: datetime
    round: RoundDetailResponse


EventResponse = Annotated[
    UserEventResponse | RoundEndedEventResponse | RoundEventResponse,
    Field(discriminator="type"),
]


class MatchEventsResponse(BaseModel):
    match: MatchSummaryResponse
    events: list[EventResponse]


@router.get(
    "/users/{user_id}/ranked-play/matches",
    response_model=response.BaseResponse[UserMatchesResponse],
)
async def get_user_matches(
    ctx: OptionalAuth,
    user_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
) -> Response:
    result = await ranked_play.get_user_matches(
        ctx,
        user_id,
        page,
        limit,
        viewer=ctx.session,
    )
    result = response.unwrap(result)

    return response.create(UserMatchesResponse.model_validate(asdict(result)))


@router.get(
    "/ranked-play/matches/{match_id}",
    response_model=response.BaseResponse[MatchDetailResponse],
)
async def get_match(ctx: RequiresContext, match_id: int) -> Response:
    result = await ranked_play.get_match(ctx, match_id)
    result = response.unwrap(result)

    return response.create(MatchDetailResponse.model_validate(asdict(result)))


@router.get(
    "/ranked-play/matches/{match_id}/events",
    response_model=response.BaseResponse[MatchEventsResponse],
)
async def get_match_events(ctx: RequiresContext, match_id: int) -> Response:
    result = await ranked_play.get_match_events(ctx, match_id)
    result = response.unwrap(result)

    return response.create(MatchEventsResponse.model_validate(asdict(result)))
