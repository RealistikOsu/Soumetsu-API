from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresAuth
from soumetsu_api.api.v2.context import RequiresAuthTransaction
from soumetsu_api.services import friends

router = APIRouter(prefix="/users/me/friends")


class FriendResponse(BaseModel):
    user_id: int
    username: str
    country: str


class RelationshipsResponse(BaseModel):
    friends: list[FriendResponse]
    followers: list[FriendResponse]
    mutual: list[int]


class IsFriendResponse(BaseModel):
    is_friend: bool


def _to_response(f: friends.FriendResult) -> FriendResponse:
    return FriendResponse(
        user_id=f.user_id,
        username=f.username,
        country=f.country,
    )


@router.get("/", response_model=response.BaseResponse[list[FriendResponse]])
async def get_friends(
    ctx: RequiresAuth,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await friends.get_friends(ctx, ctx.user_id, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(f) for f in result])


@router.get(
    "/relationships",
    response_model=response.BaseResponse[RelationshipsResponse],
)
async def get_relationships(
    ctx: RequiresAuth,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await friends.get_relationships(ctx, ctx.user_id, page, limit)
    result = response.unwrap(result)

    return response.create(
        RelationshipsResponse(
            friends=[_to_response(f) for f in result.friends],
            followers=[_to_response(f) for f in result.followers],
            mutual=result.mutual,
        ),
    )


@router.get("/{user_id}", response_model=response.BaseResponse[IsFriendResponse])
async def is_friend(
    ctx: RequiresAuth,
    user_id: int,
) -> Response:
    result = await friends.is_friend(ctx, ctx.user_id, user_id)
    result = response.unwrap(result)

    return response.create(IsFriendResponse(is_friend=result))


@router.post("/{user_id}", response_model=response.BaseResponse[None])
async def add_friend(
    ctx: RequiresAuthTransaction,
    user_id: int,
) -> Response:
    result = await friends.add_friend(ctx, ctx.user_id, user_id)
    response.unwrap(result)

    return response.create(None)


@router.delete("/{user_id}", response_model=response.BaseResponse[None])
async def remove_friend(
    ctx: RequiresAuthTransaction,
    user_id: int,
) -> Response:
    result = await friends.remove_friend(ctx, ctx.user_id, user_id)
    response.unwrap(result)

    return response.create(None)
