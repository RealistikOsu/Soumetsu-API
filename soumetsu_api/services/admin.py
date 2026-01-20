from __future__ import annotations

from typing import override

from fastapi import status

from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import privileges


class AdminError(ServiceError):
    USER_NOT_FOUND = "user_not_found"
    FORBIDDEN = "forbidden"
    INVALID_MODE = "invalid_mode"
    INVALID_CUSTOM_MODE = "invalid_custom_mode"

    @override
    def service(self) -> str:
        return "admin"

    @override
    def status_code(self) -> int:
        match self:
            case AdminError.USER_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case AdminError.FORBIDDEN:
                return status.HTTP_403_FORBIDDEN
            case AdminError.INVALID_MODE | AdminError.INVALID_CUSTOM_MODE:
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


def check_admin(user_privileges: int, required: privileges.UserPrivileges) -> bool:
    user_privs = privileges.UserPrivileges(user_privileges)
    return privileges.has_privilege(user_privs, required)


async def create_rap_log(
    ctx: AbstractContext,
    admin_id: int,
    admin_privileges: int,
    text: str,
    through: str = "soumetsu-api",
) -> AdminError.OnSuccess[int]:
    if not check_admin(admin_privileges, privileges.UserPrivileges.ADMIN_ACCESS_RAP):
        return AdminError.FORBIDDEN

    log_id = await ctx.admin.create_rap_log(admin_id, text, through)
    return log_id


async def ban_user(
    ctx: AbstractContext,
    admin_id: int,
    admin_privileges: int,
    user_id: int,
    reason: str = "",
) -> AdminError.OnSuccess[None]:
    if not check_admin(admin_privileges, privileges.UserPrivileges.ADMIN_BAN_USERS):
        return AdminError.FORBIDDEN

    user = await ctx.users.find_by_id(user_id)
    if not user:
        return AdminError.USER_NOT_FOUND

    await ctx.admin.ban_user(user_id, reason)
    await ctx.admin.create_rap_log(
        admin_id,
        f"Banned {user.username} (reason: {reason})",
        "soumetsu-api",
    )

    return None


async def restrict_user(
    ctx: AbstractContext,
    admin_id: int,
    admin_privileges: int,
    user_id: int,
    reason: str = "",
) -> AdminError.OnSuccess[None]:
    if not check_admin(admin_privileges, privileges.UserPrivileges.ADMIN_BAN_USERS):
        return AdminError.FORBIDDEN

    user = await ctx.users.find_by_id(user_id)
    if not user:
        return AdminError.USER_NOT_FOUND

    await ctx.admin.restrict_user(user_id, reason)
    await ctx.admin.create_rap_log(
        admin_id,
        f"Restricted {user.username} (reason: {reason})",
        "soumetsu-api",
    )

    return None


async def unrestrict_user(
    ctx: AbstractContext,
    admin_id: int,
    admin_privileges: int,
    user_id: int,
) -> AdminError.OnSuccess[None]:
    if not check_admin(admin_privileges, privileges.UserPrivileges.ADMIN_BAN_USERS):
        return AdminError.FORBIDDEN

    user = await ctx.users.find_by_id(user_id)
    if not user:
        return AdminError.USER_NOT_FOUND

    await ctx.admin.unrestrict_user(user_id)
    await ctx.admin.create_rap_log(
        admin_id,
        f"Unrestricted {user.username}",
        "soumetsu-api",
    )

    return None


async def update_user(
    ctx: AbstractContext,
    admin_id: int,
    admin_privileges: int,
    user_id: int,
    username: str | None = None,
    email: str | None = None,
    country: str | None = None,
    silence_end: int | None = None,
    notes: str | None = None,
) -> AdminError.OnSuccess[None]:
    if not check_admin(admin_privileges, privileges.UserPrivileges.ADMIN_MANAGE_USERS):
        return AdminError.FORBIDDEN

    user = await ctx.users.find_by_id(user_id)
    if not user:
        return AdminError.USER_NOT_FOUND

    await ctx.admin.update_user(
        user_id,
        username,
        email,
        country,
        silence_end,
        notes,
    )

    changes = []
    if username:
        changes.append(f"username={username}")
    if email:
        changes.append(f"email={email}")
    if country:
        changes.append(f"country={country}")
    if silence_end is not None:
        changes.append(f"silence_end={silence_end}")

    if changes:
        await ctx.admin.create_rap_log(
            admin_id,
            f"Updated {user.username}: {', '.join(changes)}",
            "soumetsu-api",
        )

    return None


async def wipe_user_stats(
    ctx: AbstractContext,
    admin_id: int,
    admin_privileges: int,
    user_id: int,
    mode: int | None = None,
    custom_mode: int = 0,
) -> AdminError.OnSuccess[None]:
    if not check_admin(admin_privileges, privileges.UserPrivileges.ADMIN_WIPE_USERS):
        return AdminError.FORBIDDEN

    if mode is not None and (mode < 0 or mode > 3):
        return AdminError.INVALID_MODE

    if custom_mode < 0 or custom_mode > 2:
        return AdminError.INVALID_CUSTOM_MODE

    user = await ctx.users.find_by_id(user_id)
    if not user:
        return AdminError.USER_NOT_FOUND

    await ctx.admin.wipe_user_stats(user_id, mode, custom_mode)

    mode_name = ["std", "taiko", "ctb", "mania"][mode] if mode is not None else "all"
    custom_mode_name = ["vanilla", "relax", "autopilot"][custom_mode]

    await ctx.admin.create_rap_log(
        admin_id,
        f"Wiped {user.username}'s {mode_name} stats ({custom_mode_name})",
        "soumetsu-api",
    )

    return None
