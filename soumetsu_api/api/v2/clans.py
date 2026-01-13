from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresAuth
from soumetsu_api.api.v2.context import RequiresAuthTransaction
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import clans

router = APIRouter(prefix="/clans")


class ClanResponse(BaseModel):
    id: int
    name: str
    description: str
    icon: str
    tag: str
    member_limit: int
    member_count: int


class ClanMemberResponse(BaseModel):
    user_id: int
    username: str
    country: str
    is_owner: bool


class CreateClanRequest(BaseModel):
    name: str
    tag: str
    description: str = ""


class UpdateClanRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None


class JoinClanRequest(BaseModel):
    invite: str


class InviteResponse(BaseModel):
    invite: str


def _to_response(c: clans.ClanResult) -> ClanResponse:
    return ClanResponse(
        id=c.id,
        name=c.name,
        description=c.description,
        icon=c.icon,
        tag=c.tag,
        member_limit=c.member_limit,
        member_count=c.member_count,
    )


def _member_to_response(m: clans.ClanMemberResult) -> ClanMemberResponse:
    return ClanMemberResponse(
        user_id=m.user_id,
        username=m.username,
        country=m.country,
        is_owner=m.is_owner,
    )


@router.get("/", response_model=response.BaseResponse[list[ClanResponse]])
async def search_clans(
    ctx: RequiresContext,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await clans.search_clans(ctx, q, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(c) for c in result])


@router.post("/", response_model=response.BaseResponse[ClanResponse])
async def create_clan(
    ctx: RequiresAuthTransaction,
    body: CreateClanRequest,
) -> Response:
    result = await clans.create_clan(
        ctx,
        ctx.user_id,
        body.name,
        body.tag,
        body.description,
    )
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.get("/{clan_id}", response_model=response.BaseResponse[ClanResponse])
async def get_clan(
    ctx: RequiresContext,
    clan_id: int,
) -> Response:
    result = await clans.get_clan(ctx, clan_id)
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.put("/{clan_id}", response_model=response.BaseResponse[ClanResponse])
async def update_clan(
    ctx: RequiresAuthTransaction,
    clan_id: int,
    body: UpdateClanRequest,
) -> Response:
    result = await clans.update_clan(
        ctx,
        ctx.user_id,
        clan_id,
        body.name,
        body.description,
        body.icon,
    )
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.delete("/{clan_id}", response_model=response.BaseResponse[None])
async def delete_clan(
    ctx: RequiresAuthTransaction,
    clan_id: int,
) -> Response:
    result = await clans.delete_clan(ctx, ctx.user_id, clan_id)
    response.unwrap(result)

    return response.create(None)


@router.get(
    "/{clan_id}/members",
    response_model=response.BaseResponse[list[ClanMemberResponse]],
)
async def get_members(
    ctx: RequiresContext,
    clan_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await clans.get_members(ctx, clan_id, page, limit)
    result = response.unwrap(result)

    return response.create([_member_to_response(m) for m in result])


@router.post("/join", response_model=response.BaseResponse[ClanResponse])
async def join_clan_by_invite(
    ctx: RequiresAuthTransaction,
    invite: str = Query(..., min_length=1),
) -> Response:
    result = await clans.join_clan(ctx, ctx.user_id, invite)
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.post("/{clan_id}/join", response_model=response.BaseResponse[ClanResponse])
async def join_clan(
    ctx: RequiresAuthTransaction,
    clan_id: int,
    body: JoinClanRequest,
) -> Response:
    result = await clans.join_clan(ctx, ctx.user_id, body.invite)
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.delete("/{clan_id}/members/me", response_model=response.BaseResponse[None])
async def leave_clan(
    ctx: RequiresAuthTransaction,
    clan_id: int,
) -> Response:
    result = await clans.leave_clan(ctx, ctx.user_id, clan_id)
    response.unwrap(result)

    return response.create(None)


@router.delete(
    "/{clan_id}/members/{user_id}",
    response_model=response.BaseResponse[None],
)
async def kick_member(
    ctx: RequiresAuthTransaction,
    clan_id: int,
    user_id: int,
) -> Response:
    result = await clans.kick_member(ctx, ctx.user_id, clan_id, user_id)
    response.unwrap(result)

    return response.create(None)


@router.get("/{clan_id}/invite", response_model=response.BaseResponse[InviteResponse])
async def get_invite(
    ctx: RequiresAuth,
    clan_id: int,
) -> Response:
    result = await clans.get_invite(ctx, ctx.user_id, clan_id)
    result = response.unwrap(result)

    return response.create(InviteResponse(invite=result))


@router.post("/{clan_id}/invite", response_model=response.BaseResponse[InviteResponse])
async def regenerate_invite(
    ctx: RequiresAuthTransaction,
    clan_id: int,
) -> Response:
    result = await clans.regenerate_invite(ctx, ctx.user_id, clan_id)
    result = response.unwrap(result)

    return response.create(InviteResponse(invite=result))
