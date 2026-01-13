from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import badges

router = APIRouter(prefix="/badges")


class BadgeResponse(BaseModel):
    id: int
    name: str
    icon: str


class BadgeMemberResponse(BaseModel):
    user_id: int
    username: str
    country: str


@router.get("/", response_model=response.BaseResponse[list[BadgeResponse]])
async def get_badges(
    ctx: RequiresContext,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await badges.get_badges(ctx, page, limit)
    result = response.unwrap(result)

    return response.create(
        [BadgeResponse(id=b.id, name=b.name, icon=b.icon) for b in result],
    )


@router.get("/{badge_id}", response_model=response.BaseResponse[BadgeResponse])
async def get_badge(
    ctx: RequiresContext,
    badge_id: int,
) -> Response:
    result = await badges.get_badge(ctx, badge_id)
    result = response.unwrap(result)

    return response.create(
        BadgeResponse(
            id=result.id,
            name=result.name,
            icon=result.icon,
        ),
    )


@router.get(
    "/{badge_id}/members",
    response_model=response.BaseResponse[list[BadgeMemberResponse]],
)
async def get_badge_members(
    ctx: RequiresContext,
    badge_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await badges.get_badge_members(ctx, badge_id, page, limit)
    result = response.unwrap(result)

    return response.create(
        [
            BadgeMemberResponse(
                user_id=m.user_id,
                username=m.username,
                country=m.country,
            )
            for m in result
        ],
    )
