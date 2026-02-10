from __future__ import annotations

import time
from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.resources import SessionData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import crypto
from soumetsu_api.utilities import privileges
from soumetsu_api.utilities import validation


class AuthError(ServiceError):
    USER_NOT_FOUND = "user_not_found"
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_RESTRICTED = "account_restricted"
    ACCOUNT_PENDING = "account_pending"
    PASSWORD_VERSION_OLD = "password_version_old"
    USERNAME_TAKEN = "username_taken"
    EMAIL_TAKEN = "email_taken"
    USERNAME_RESERVED = "username_reserved"
    INVALID_CAPTCHA = "invalid_captcha"
    VALIDATION_ERROR = "validation_error"

    @override
    def service(self) -> str:
        return "auth"

    @override
    def status_code(self) -> int:
        match self:
            case AuthError.USER_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case (
                AuthError.INVALID_CREDENTIALS
                | AuthError.ACCOUNT_RESTRICTED
                | AuthError.ACCOUNT_PENDING
                | AuthError.PASSWORD_VERSION_OLD
            ):
                return status.HTTP_403_FORBIDDEN
            case (
                AuthError.USERNAME_TAKEN
                | AuthError.EMAIL_TAKEN
                | AuthError.USERNAME_RESERVED
            ):
                return status.HTTP_409_CONFLICT
            case AuthError.INVALID_CAPTCHA | AuthError.VALIDATION_ERROR:
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class LoginResult:
    token: str
    user_id: int
    username: str
    privileges: int


async def login(
    ctx: AbstractContext,
    identifier: str,
    password: str,
    ip_address: str,
) -> AuthError.OnSuccess[LoginResult]:
    user = await ctx.users.find_for_login(identifier)
    if not user:
        return AuthError.USER_NOT_FOUND

    if user.password_version == 1:
        return AuthError.PASSWORD_VERSION_OLD

    if not await crypto.verify_password(password, user.password_md5):
        return AuthError.INVALID_CREDENTIALS

    user_privs = privileges.UserPrivileges(user.privileges)

    if privileges.is_pending_verification(user_privs):
        return AuthError.ACCOUNT_PENDING

    if privileges.is_restricted(user_privs):
        return AuthError.ACCOUNT_RESTRICTED

    token = await ctx.sessions.create(
        user_id=user.id,
        privileges=user.privileges,
        ip_address=ip_address,
    )

    return LoginResult(
        token=token,
        user_id=user.id,
        username=user.username,
        privileges=user.privileges,
    )


@dataclass
class RegisterResult:
    user_id: int
    username: str


async def register(
    ctx: AbstractContext,
    username: str,
    email: str,
    password: str,
) -> AuthError.OnSuccess[RegisterResult]:
    try:
        validation.validate_username(username)
    except validation.ValidationError:
        return AuthError.VALIDATION_ERROR

    try:
        validation.validate_password(password)
    except validation.ValidationError:
        return AuthError.VALIDATION_ERROR

    if await ctx.users.username_exists(username):
        return AuthError.USERNAME_TAKEN

    if await ctx.users.email_exists(email):
        return AuthError.EMAIL_TAKEN

    if await ctx.users.username_in_history(username):
        return AuthError.USERNAME_RESERVED

    password_hash = await crypto.hash_password(password)
    api_key = crypto.generate_token(64)

    initial_privileges = (
        privileges.UserPrivileges.PUBLIC
        | privileges.UserPrivileges.NORMAL
        | privileges.UserPrivileges.PENDING_VERIFICATION
    )

    user_id = await ctx.users.create(
        username=username,
        email=email,
        password_hash=password_hash,
        api_key=api_key,
        privileges=int(initial_privileges),
        registered_at=int(time.time()),
    )

    await ctx.user_stats.initialise_all(user_id, username)

    return RegisterResult(user_id=user_id, username=username)


async def logout(ctx: AbstractContext, token: str) -> AuthError.OnSuccess[None]:
    await ctx.sessions.delete(token)
    return None


async def get_session(
    ctx: AbstractContext,
    token: str,
) -> AuthError.OnSuccess[SessionData]:
    session = await ctx.sessions.get(token)
    if not session:
        return AuthError.INVALID_CREDENTIALS
    return session
