from __future__ import annotations

from fastapi import APIRouter
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.auth import LoginResponse
from soumetsu_api.api.v2.context import RequiresAuth
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import two_factor

router = APIRouter(prefix="/auth/2fa")


class StatusResponse(BaseModel):
    enabled: bool
    required: bool
    recovery_codes_left: int


class SetupRequest(BaseModel):
    # The token from the emailed link; staff can't start setup without one.
    setup_token: str | None = None


class SetupResponse(BaseModel):
    secret: str
    uri: str


class CodeRequest(BaseModel):
    code: str


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class LoginCodeRequest(BaseModel):
    challenge: str
    code: str


@router.get("", response_model=response.BaseResponse[StatusResponse])
async def get_status(ctx: RequiresAuth) -> Response:
    result = await two_factor.get_status(ctx, ctx.user_id)
    return response.create(
        StatusResponse(
            enabled=result.enabled,
            required=result.required,
            recovery_codes_left=result.recovery_codes_left,
        ),
    )


@router.post("/setup-link", response_model=response.BaseResponse[None])
async def send_setup_link(ctx: RequiresAuth) -> Response:
    response.unwrap(await two_factor.send_setup_link(ctx, ctx.user_id))
    return response.create(None)


@router.post("/setup", response_model=response.BaseResponse[SetupResponse])
async def start_setup(ctx: RequiresAuth, body: SetupRequest) -> Response:
    result = response.unwrap(
        await two_factor.start_setup(ctx, ctx.user_id, body.setup_token),
    )
    return response.create(SetupResponse(secret=result.secret, uri=result.uri))


@router.post(
    "/setup/confirm",
    response_model=response.BaseResponse[RecoveryCodesResponse],
)
async def confirm_setup(ctx: RequiresAuth, body: CodeRequest) -> Response:
    token = ctx.request.headers.get("Authorization", "")[7:]
    codes = response.unwrap(
        await two_factor.confirm_setup(ctx, ctx.user_id, token, body.code),
    )
    return response.create(RecoveryCodesResponse(recovery_codes=codes))


@router.post(
    "/recovery-codes",
    response_model=response.BaseResponse[RecoveryCodesResponse],
)
async def regenerate_recovery_codes(ctx: RequiresAuth, body: CodeRequest) -> Response:
    codes = response.unwrap(
        await two_factor.regenerate_recovery_codes(ctx, ctx.user_id, body.code),
    )
    return response.create(RecoveryCodesResponse(recovery_codes=codes))


@router.post("/disable", response_model=response.BaseResponse[None])
async def disable(ctx: RequiresAuth, body: CodeRequest) -> Response:
    response.unwrap(await two_factor.disable(ctx, ctx.user_id, body.code))
    return response.create(None)


@router.post("/login", response_model=response.BaseResponse[LoginResponse])
async def login(ctx: RequiresContext, body: LoginCodeRequest) -> Response:
    result = response.unwrap(
        await two_factor.verify_login(ctx, body.challenge, body.code),
    )
    return response.create(
        LoginResponse(
            token=result.token,
            user_id=result.user_id,
            username=result.username,
            privileges=result.privileges,
        ),
    )
