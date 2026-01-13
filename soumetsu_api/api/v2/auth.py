from __future__ import annotations

from fastapi import APIRouter
from fastapi import Request
from fastapi import Response
from fastapi import status
from pydantic import BaseModel

from soumetsu_api.adapters import hcaptcha
from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresAuth
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import auth
from soumetsu_api.services.auth import AuthError


router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    identifier: str
    password: str
    captcha_token: str | None = None


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str
    privileges: int


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    captcha_token: str | None = None


class RegisterResponse(BaseModel):
    user_id: int
    username: str


class SessionResponse(BaseModel):
    user_id: int
    privileges: int
    created_at: int
    expires_at: int


@router.post("/login", response_model=response.BaseResponse[LoginResponse])
async def login(
    request: Request,
    ctx: RequiresContext,
    body: LoginRequest,
) -> Response:
    if body.captcha_token:
        captcha_valid = await hcaptcha.verify_token(
            body.captcha_token,
            request.client.host if request.client else None,
        )
        if not captcha_valid:
            return response.create(
                data=AuthError.INVALID_CAPTCHA.resolve_name(),
                status=AuthError.INVALID_CAPTCHA.status_code(),
            )

    ip_address = request.client.host if request.client else "unknown"

    result = await auth.login(
        ctx,
        identifier=body.identifier,
        password=body.password,
        ip_address=ip_address,
    )
    result = response.unwrap(result)

    return response.create(
        LoginResponse(
            token=result.token,
            user_id=result.user_id,
            username=result.username,
            privileges=result.privileges,
        )
    )


@router.post("/logout", response_model=response.BaseResponse[None])
async def logout(ctx: RequiresAuth) -> Response:
    token = ctx.request.headers.get("Authorization", "")[7:]
    await auth.logout(ctx, token)
    return response.create(None)


@router.post("/register", response_model=response.BaseResponse[RegisterResponse])
async def register(
    request: Request,
    ctx: RequiresContext,
    body: RegisterRequest,
) -> Response:
    if body.captcha_token:
        captcha_valid = await hcaptcha.verify_token(
            body.captcha_token,
            request.client.host if request.client else None,
        )
        if not captcha_valid:
            return response.create(
                data=AuthError.INVALID_CAPTCHA.resolve_name(),
                status=AuthError.INVALID_CAPTCHA.status_code(),
            )

    result = await auth.register(
        ctx,
        username=body.username,
        email=body.email,
        password=body.password,
    )
    result = response.unwrap(result)

    return response.create(
        RegisterResponse(
            user_id=result.user_id,
            username=result.username,
        )
    )


@router.get("/session", response_model=response.BaseResponse[SessionResponse])
async def get_session(ctx: RequiresAuth) -> Response:
    return response.create(
        SessionResponse(
            user_id=ctx.session.user_id,
            privileges=ctx.session.privileges,
            created_at=ctx.session.created_at,
            expires_at=ctx.session.expires_at,
        )
    )


@router.delete(
    "/session",
    response_model=response.BaseResponse[None],
    status_code=status.HTTP_200_OK,
)
async def revoke_session(ctx: RequiresAuth) -> Response:
    token = ctx.request.headers.get("Authorization", "")[7:]
    await auth.logout(ctx, token)
    return response.create(None)
