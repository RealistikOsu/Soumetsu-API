from __future__ import annotations

from fastapi import APIRouter
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresAuthTransaction
from soumetsu_api.services import admin

router = APIRouter(prefix="/admin")


class CreateLogRequest(BaseModel):
    text: str
    through: str = "soumetsu-api"


class LogResponse(BaseModel):
    log_id: int


class UserStatusRequest(BaseModel):
    action: str  # "ban", "restrict", "unrestrict"
    reason: str = ""


class UpdateUserRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    country: str | None = None
    silence_end: int | None = None
    notes: str | None = None


class WipeStatsRequest(BaseModel):
    mode: int | None = None
    custom_mode: int = 0


@router.post("/logs", response_model=response.BaseResponse[LogResponse])
async def create_log(
    ctx: RequiresAuthTransaction,
    body: CreateLogRequest,
) -> Response:
    result = await admin.create_rap_log(
        ctx,
        ctx.user_id,
        ctx.privileges,
        body.text,
        body.through,
    )
    result = response.unwrap(result)

    return response.create(LogResponse(log_id=result))


@router.put(
    "/users/{user_id}/status",
    response_model=response.BaseResponse[None],
)
async def update_user_status(
    ctx: RequiresAuthTransaction,
    user_id: int,
    body: UserStatusRequest,
) -> Response:
    match body.action:
        case "ban":
            result = await admin.ban_user(
                ctx,
                ctx.user_id,
                ctx.privileges,
                user_id,
                body.reason,
            )
        case "restrict":
            result = await admin.restrict_user(
                ctx,
                ctx.user_id,
                ctx.privileges,
                user_id,
                body.reason,
            )
        case "unrestrict":
            result = await admin.unrestrict_user(
                ctx,
                ctx.user_id,
                ctx.privileges,
                user_id,
            )
        case _:
            return response.create(
                data="admin.invalid_action",
                status=400,
            )

    response.unwrap(result)
    return response.create(None)


@router.patch(
    "/users/{user_id}",
    response_model=response.BaseResponse[None],
)
async def update_user(
    ctx: RequiresAuthTransaction,
    user_id: int,
    body: UpdateUserRequest,
) -> Response:
    result = await admin.update_user(
        ctx,
        ctx.user_id,
        ctx.privileges,
        user_id,
        body.username,
        body.email,
        body.country,
        body.silence_end,
        body.notes,
    )
    response.unwrap(result)

    return response.create(None)


@router.post(
    "/users/{user_id}/wipe",
    response_model=response.BaseResponse[None],
)
async def wipe_user_stats(
    ctx: RequiresAuthTransaction,
    user_id: int,
    body: WipeStatsRequest,
) -> Response:
    result = await admin.wipe_user_stats(
        ctx,
        ctx.user_id,
        ctx.privileges,
        user_id,
        body.mode,
        body.custom_mode,
    )
    response.unwrap(result)

    return response.create(None)
