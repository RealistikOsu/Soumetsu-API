from __future__ import annotations

from fastapi import APIRouter
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import team

router = APIRouter(prefix="/team")


class TeamMemberResponse(BaseModel):
    id: int
    username: str
    country: str
    privileges: int
    global_rank: int
    country_rank: int
    is_online: bool
    pp: int
    accuracy: float
    mode: int
    custom_mode: int


class TeamGroupResponse(BaseModel):
    badge_id: int
    name: str
    members: list[TeamMemberResponse]


class TeamResponse(BaseModel):
    groups: list[TeamGroupResponse]


@router.get("/", response_model=response.BaseResponse[TeamResponse])
async def get_team(ctx: RequiresContext) -> Response:
    """Get all team groups with member card data."""
    result = await team.get_team(ctx)
    result = response.unwrap(result)

    return response.create(
        TeamResponse(
            groups=[
                TeamGroupResponse(
                    badge_id=group.badge_id,
                    name=group.name,
                    members=[
                        TeamMemberResponse(
                            id=m.id,
                            username=m.username,
                            country=m.country,
                            privileges=m.privileges,
                            global_rank=m.global_rank,
                            country_rank=m.country_rank,
                            is_online=m.is_online,
                            pp=m.pp,
                            accuracy=m.accuracy,
                            mode=m.mode,
                            custom_mode=m.custom_mode,
                        )
                        for m in group.members
                    ],
                )
                for group in result.groups
            ],
        ),
    )
