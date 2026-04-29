from __future__ import annotations

from fastapi import APIRouter
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import stats

router = APIRouter(prefix="/stats")


class StatsResponse(BaseModel):
    online_users: int
    registered_users: int


@router.get("/", response_model=response.BaseResponse[StatsResponse])
async def get_stats(
    ctx: RequiresContext,
) -> Response:
    result = await stats.get_stats(ctx)
    result = response.unwrap(result)

    return response.create(
        StatsResponse(
            online_users=result.online_users,
            registered_users=result.registered_users,
        ),
    )
