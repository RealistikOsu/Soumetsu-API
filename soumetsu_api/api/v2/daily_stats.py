from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import OptionalAuth
from soumetsu_api.services import daily_stats

router = APIRouter()


class DailyStatsResponse(BaseModel):
    total_days: int
    current_daily_streak: int
    current_weekly_streak: int
    best_daily_streak: int
    best_weekly_streak: int
    top_10_placements: int
    top_50_placements: int


@router.get(
    "/users/{user_id}/daily-challenge",
    response_model=response.BaseResponse[DailyStatsResponse],
)
async def get_user_daily_stats(ctx: OptionalAuth, user_id: int) -> Response:
    result = await daily_stats.get_user_stats(ctx, user_id, viewer=ctx.session)
    result = response.unwrap(result)

    return response.create(DailyStatsResponse.model_validate(asdict(result)))
