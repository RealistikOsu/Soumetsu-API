from __future__ import annotations

import time
from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api import settings
from soumetsu_api.adapters import mail
from soumetsu_api.resources.two_factor import TwoFactorData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.services.auth import LoginResult
from soumetsu_api.utilities import logging
from soumetsu_api.utilities import privileges
from soumetsu_api.utilities import totp

logger = logging.get_logger(__name__)


class TwoFactorError(ServiceError):
    NOT_ENABLED = "not_enabled"
    ALREADY_ENABLED = "already_enabled"
    SETUP_LINK_REQUIRED = "setup_link_required"
    INVALID_SETUP_LINK = "invalid_setup_link"
    NOT_STARTED = "not_started"
    INVALID_CODE = "invalid_code"
    CHALLENGE_EXPIRED = "challenge_expired"
    REQUIRED_FOR_STAFF = "required_for_staff"
    MAIL_FAILED = "mail_failed"

    @override
    def service(self) -> str:
        return "two_factor"

    @override
    def status_code(self) -> int:
        match self:
            case TwoFactorError.INVALID_CODE | TwoFactorError.INVALID_SETUP_LINK:
                return status.HTTP_400_BAD_REQUEST
            case TwoFactorError.CHALLENGE_EXPIRED:
                return status.HTTP_401_UNAUTHORIZED
            case TwoFactorError.SETUP_LINK_REQUIRED | TwoFactorError.REQUIRED_FOR_STAFF:
                return status.HTTP_403_FORBIDDEN
            case TwoFactorError.NOT_ENABLED | TwoFactorError.NOT_STARTED:
                return status.HTTP_404_NOT_FOUND
            case TwoFactorError.ALREADY_ENABLED:
                return status.HTTP_409_CONFLICT
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class TwoFactorStatus:
    enabled: bool
    # Staff can't use their privileges without it, so they can't turn it off either.
    required: bool
    recovery_codes_left: int


@dataclass
class SetupStart:
    secret: str
    uri: str


async def get_status(ctx: AbstractContext, user_id: int) -> TwoFactorStatus:
    data = await ctx.two_factor.get(user_id)
    enabled = data is not None and data.confirmed
    return TwoFactorStatus(
        enabled=enabled,
        required=privileges.is_staff(await ctx.users.get_privileges(user_id)),
        recovery_codes_left=(
            await ctx.two_factor.recovery_codes_left(user_id) if enabled else 0
        ),
    )


# Staff confirm setting up two-factor from their email, so someone who got in with only the password (a
# guessed or reset one) can't attach their own authenticator to a staff account.
async def send_setup_link(
    ctx: AbstractContext,
    user_id: int,
) -> TwoFactorError.OnSuccess[None]:
    data = await ctx.two_factor.get(user_id)
    if data and data.confirmed:
        return TwoFactorError.ALREADY_ENABLED

    email = await ctx.users.get_email(user_id)
    user = await ctx.users.find_by_id(user_id)
    if not email or not user:
        logger.warning(
            "No email to send the two-factor setup link to.",
            extra={"user_id": user_id},
        )
        return TwoFactorError.MAIL_FAILED

    token = await ctx.two_factor.create_setup_token(user_id)
    link = f"{settings.APP_BASE_URL}/settings/2fa?setup={token}"
    try:
        await mail.send(
            email,
            "RealistikOsu - Set up two-factor authentication",
            f"Hey {user.username}!<br><br>Someone (hopefully you) asked to set up two-factor "
            f"authentication on your RealistikOsu account. <a href='{link}'>Click here</a> to "
            "continue. The link works for 30 minutes.<br><br>If this wasn't you, your password may "
            "be known to someone else: change it, and let the staff team know.",
        )
    except mail.MailError as error:
        logger.warning(
            "Could not send the two-factor setup link.",
            extra={"user_id": user_id, "error": str(error)},
        )
        return TwoFactorError.MAIL_FAILED
    return None


async def start_setup(
    ctx: AbstractContext,
    user_id: int,
    setup_token: str | None,
) -> TwoFactorError.OnSuccess[SetupStart]:
    data = await ctx.two_factor.get(user_id)
    if data and data.confirmed:
        return TwoFactorError.ALREADY_ENABLED

    if privileges.is_staff(await ctx.users.get_privileges(user_id)):
        if not setup_token:
            return TwoFactorError.SETUP_LINK_REQUIRED
        if await ctx.two_factor.take_setup_token(setup_token) != user_id:
            return TwoFactorError.INVALID_SETUP_LINK

    user = await ctx.users.find_by_id(user_id)
    if not user:
        return TwoFactorError.NOT_STARTED

    secret = totp.new_secret()
    await ctx.two_factor.start(user_id, totp.encrypt(secret), int(time.time()))
    return SetupStart(secret=secret, uri=totp.provisioning_uri(secret, user.username))


async def _code_matches(
    ctx: AbstractContext,
    data: TwoFactorData,
    code: str,
    allow_recovery: bool,
) -> bool:
    step = totp.matching_step(totp.decrypt(data.secret), code)
    if step is not None:
        return await ctx.two_factor.use_step(data.user_id, step)
    if not allow_recovery:
        return False
    return await ctx.two_factor.use_recovery_code(
        data.user_id,
        totp.hash_recovery_code(code),
        int(time.time()),
    )


# The first correct code turns it on, gives out the recovery codes, and upgrades the session it was set up in.
async def confirm_setup(
    ctx: AbstractContext,
    user_id: int,
    session_token: str,
    code: str,
) -> TwoFactorError.OnSuccess[list[str]]:
    data = await ctx.two_factor.get(user_id)
    if not data:
        return TwoFactorError.NOT_STARTED
    if data.confirmed:
        return TwoFactorError.ALREADY_ENABLED
    if not await _code_matches(ctx, data, code, allow_recovery=False):
        return TwoFactorError.INVALID_CODE

    await ctx.two_factor.confirm(user_id)
    codes = totp.new_recovery_codes()
    await ctx.two_factor.replace_recovery_codes(
        user_id,
        [totp.hash_recovery_code(c) for c in codes],
    )
    await ctx.sessions.mark_mfa(session_token)
    return codes


async def disable(
    ctx: AbstractContext,
    user_id: int,
    code: str,
) -> TwoFactorError.OnSuccess[None]:
    if privileges.is_staff(await ctx.users.get_privileges(user_id)):
        return TwoFactorError.REQUIRED_FOR_STAFF
    data = await ctx.two_factor.get(user_id)
    if not data or not data.confirmed:
        return TwoFactorError.NOT_ENABLED
    if not await _code_matches(ctx, data, code, allow_recovery=True):
        return TwoFactorError.INVALID_CODE
    await ctx.two_factor.delete(user_id)
    return None


async def regenerate_recovery_codes(
    ctx: AbstractContext,
    user_id: int,
    code: str,
) -> TwoFactorError.OnSuccess[list[str]]:
    data = await ctx.two_factor.get(user_id)
    if not data or not data.confirmed:
        return TwoFactorError.NOT_ENABLED
    if not await _code_matches(ctx, data, code, allow_recovery=False):
        return TwoFactorError.INVALID_CODE
    codes = totp.new_recovery_codes()
    await ctx.two_factor.replace_recovery_codes(
        user_id,
        [totp.hash_recovery_code(c) for c in codes],
    )
    return codes


# Second step of logging in: the challenge from the password step plus an authenticator or recovery code.
async def verify_login(
    ctx: AbstractContext,
    challenge_token: str,
    code: str,
) -> TwoFactorError.OnSuccess[LoginResult]:
    challenge = await ctx.two_factor.get_challenge(challenge_token)
    if not challenge:
        return TwoFactorError.CHALLENGE_EXPIRED

    data = await ctx.two_factor.get(challenge.user_id)
    user = await ctx.users.find_by_id(challenge.user_id)
    if not data or not data.confirmed or not user:
        await ctx.two_factor.end_challenge(challenge_token)
        return TwoFactorError.CHALLENGE_EXPIRED

    if not await _code_matches(ctx, data, code, allow_recovery=True):
        await ctx.two_factor.fail_challenge(challenge_token, challenge)
        return TwoFactorError.INVALID_CODE

    await ctx.two_factor.end_challenge(challenge_token)
    token = await ctx.sessions.create(
        user_id=user.id,
        privileges=user.privileges,
        ip_address=challenge.ip_address,
        mfa=True,
    )
    return LoginResult(
        token=token,
        user_id=user.id,
        username=user.username,
        privileges=user.privileges,
    )
