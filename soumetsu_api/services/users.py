from __future__ import annotations

import re
from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api import settings
from soumetsu_api.constants import is_valid_custom_mode
from soumetsu_api.constants import is_valid_mode
from soumetsu_api.resources.users import ClanInfo
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import crypto
from soumetsu_api.utilities import privileges


class UserError(ServiceError):
    USER_NOT_FOUND = "user_not_found"
    USER_RESTRICTED = "user_restricted"
    FORBIDDEN = "forbidden"
    USERNAME_TAKEN = "username_taken"
    USERNAME_RESERVED = "username_reserved"
    INVALID_CUSTOM_MODE = "invalid_custom_mode"
    INVALID_MODE = "invalid_mode"
    NO_DISCORD_LINKED = "no_discord_linked"
    INVALID_PASSWORD = "invalid_password"
    WEAK_PASSWORD = "weak_password"
    UPLOAD_FAILED = "upload_failed"
    INVALID_FILE_FORMAT = "invalid_file_format"
    FILE_TOO_LARGE = "file_too_large"

    @override
    def service(self) -> str:
        return "users"

    @override
    def status_code(self) -> int:
        match self:
            case UserError.USER_NOT_FOUND | UserError.NO_DISCORD_LINKED:
                return status.HTTP_404_NOT_FOUND
            case UserError.USER_RESTRICTED | UserError.FORBIDDEN:
                return status.HTTP_403_FORBIDDEN
            case UserError.USERNAME_TAKEN | UserError.USERNAME_RESERVED:
                return status.HTTP_409_CONFLICT
            case UserError.FILE_TOO_LARGE:
                return status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            case (
                UserError.INVALID_CUSTOM_MODE
                | UserError.INVALID_MODE
                | UserError.INVALID_PASSWORD
                | UserError.WEAK_PASSWORD
                | UserError.INVALID_FILE_FORMAT
                | UserError.UPLOAD_FAILED
            ):
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class UserProfile:
    id: int
    username: str
    country: str
    privileges: int
    registered_at: int
    latest_activity: int
    is_online: bool
    clan: ClanInfo | None
    stats: UserStats


@dataclass
class UserStats:
    mode: int
    custom_mode: int
    global_rank: int
    country_rank: int
    pp: int
    accuracy: float
    playcount: int
    total_score: int
    ranked_score: int
    total_hits: int
    playtime: int
    max_combo: int
    replays_watched: int
    level: int
    first_places: int


@dataclass
class UserCompact:
    id: int
    username: str
    country: str
    privileges: int


@dataclass
class UserCard:
    id: int
    username: str
    country: str
    privileges: int
    global_rank: int
    country_rank: int
    is_online: bool


async def get_card(
    ctx: AbstractContext,
    user_id: int,
) -> UserError.OnSuccess[UserCard]:
    user = await ctx.users.find_by_id(user_id)
    if not user:
        return UserError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return UserError.USER_RESTRICTED

    settings = await ctx.user_stats.get_settings(user_id)
    mode = settings.favourite_mode if settings else 0
    custom_mode = settings.prefer_relax if settings else 0

    global_rank = await ctx.leaderboard.get_user_global_rank(user_id, mode, custom_mode)
    country_rank = await ctx.leaderboard.get_user_country_rank(
        user_id,
        mode,
        custom_mode,
        user.country,
    )

    return UserCard(
        id=user.id,
        username=user.username,
        country=user.country,
        privileges=user.privileges,
        global_rank=global_rank,
        country_rank=country_rank,
        is_online=False,  # TODO: check bancho presence
    )


async def get_profile(
    ctx: AbstractContext,
    user_id: int,
    mode: int = 0,
    custom_mode: int = 0,
) -> UserError.OnSuccess[UserProfile]:
    if not is_valid_mode(mode):
        return UserError.INVALID_MODE

    if not is_valid_custom_mode(custom_mode):
        return UserError.INVALID_CUSTOM_MODE

    user = await ctx.users.find_by_id(user_id)
    if not user:
        return UserError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return UserError.USER_RESTRICTED

    stats = await ctx.user_stats.get_stats(user_id, mode, custom_mode)
    global_rank = await ctx.leaderboard.get_user_global_rank(user_id, mode, custom_mode)
    country_rank = await ctx.leaderboard.get_user_country_rank(
        user_id,
        mode,
        custom_mode,
        user.country,
    )
    first_places = await ctx.user_stats.get_first_place_count(
        user_id,
        mode,
        custom_mode,
    )

    clan_info = await ctx.users.get_clan_info(user_id)

    return UserProfile(
        id=user.id,
        username=user.username,
        country=user.country,
        privileges=user.privileges,
        registered_at=user.registered_at,
        latest_activity=user.latest_activity,
        is_online=False,  # TODO: check bancho presence
        clan=clan_info,
        stats=UserStats(
            mode=mode,
            custom_mode=custom_mode,
            global_rank=global_rank,
            country_rank=country_rank,
            pp=stats.pp if stats else 0,
            accuracy=stats.accuracy if stats else 0.0,
            playcount=stats.playcount if stats else 0,
            total_score=stats.total_score if stats else 0,
            ranked_score=stats.ranked_score if stats else 0,
            total_hits=stats.total_hits if stats else 0,
            playtime=stats.playtime if stats else 0,
            max_combo=stats.max_combo if stats else 0,
            replays_watched=stats.replays_watched if stats else 0,
            level=stats.level if stats else 1,
            first_places=first_places,
        ),
    )


async def get_by_username(
    ctx: AbstractContext,
    username: str,
) -> UserError.OnSuccess[UserCompact]:
    user = await ctx.users.find_by_username(username)
    if not user:
        return UserError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return UserError.USER_RESTRICTED

    return UserCompact(
        id=user.id,
        username=user.username,
        country=user.country,
        privileges=user.privileges,
    )


async def resolve_username(
    ctx: AbstractContext,
    username: str,
) -> UserError.OnSuccess[int]:
    user = await ctx.users.find_by_username(username)
    if not user:
        return UserError.USER_NOT_FOUND

    return user.id


async def search_users(
    ctx: AbstractContext,
    query: str,
    page: int = 1,
    limit: int = 50,
) -> UserError.OnSuccess[list[UserCompact]]:
    if limit > 100:
        limit = 100
    if page < 1:
        page = 1

    offset = (page - 1) * limit
    users = await ctx.users.search(query, limit, offset)

    return [
        UserCompact(
            id=u.id,
            username=u.username,
            country=u.country,
            privileges=u.privileges,
        )
        for u in users
        if not privileges.is_restricted(privileges.UserPrivileges(u.privileges))
    ]


@dataclass
class UserSettings:
    username_aka: str
    favourite_mode: int
    prefer_relax: int
    play_style: int
    show_country: bool
    email: str
    custom_badge_icon: str
    custom_badge_name: str
    show_custom_badge: bool
    can_custom_badge: bool
    disabled_comments: bool


async def get_settings(
    ctx: AbstractContext,
    user_id: int,
) -> UserError.OnSuccess[UserSettings]:
    stats_settings = await ctx.user_stats.get_settings(user_id)
    if not stats_settings:
        return UserError.USER_NOT_FOUND

    email = await ctx.users.get_email(user_id) or ""
    disabled_comments = await ctx.users.get_disabled_comments(user_id)

    return UserSettings(
        username_aka=stats_settings.username_aka,
        favourite_mode=stats_settings.favourite_mode,
        prefer_relax=stats_settings.prefer_relax,
        play_style=stats_settings.play_style,
        show_country=stats_settings.show_country,
        email=email,
        custom_badge_icon=stats_settings.custom_badge_icon,
        custom_badge_name=stats_settings.custom_badge_name,
        show_custom_badge=stats_settings.show_custom_badge,
        can_custom_badge=stats_settings.can_custom_badge,
        disabled_comments=disabled_comments,
    )


async def update_settings(
    ctx: AbstractContext,
    user_id: int,
    username_aka: str | None = None,
    favourite_mode: int | None = None,
    prefer_relax: int | None = None,
    play_style: int | None = None,
    show_country: bool | None = None,
    custom_badge_icon: str | None = None,
    custom_badge_name: str | None = None,
    show_custom_badge: bool | None = None,
    disabled_comments: bool | None = None,
) -> UserError.OnSuccess[None]:
    await ctx.user_stats.update_settings(
        user_id,
        username_aka=username_aka,
        favourite_mode=favourite_mode,
        prefer_relax=prefer_relax,
        play_style=play_style,
        show_country=show_country,
        custom_badge_icon=custom_badge_icon,
        custom_badge_name=custom_badge_name,
        show_custom_badge=show_custom_badge,
    )

    if disabled_comments is not None:
        await ctx.users.update_disabled_comments(user_id, disabled_comments)

    return None


async def get_userpage(
    ctx: AbstractContext,
    user_id: int,
) -> UserError.OnSuccess[str]:
    user = await ctx.users.find_by_id(user_id)
    if not user:
        return UserError.USER_NOT_FOUND

    content = await ctx.user_stats.get_userpage(user_id)
    return content or ""


async def update_userpage(
    ctx: AbstractContext,
    user_id: int,
    content: str,
) -> UserError.OnSuccess[None]:
    await ctx.user_stats.update_userpage(user_id, content)
    return None


async def change_username(
    ctx: AbstractContext,
    user_id: int,
    new_username: str,
) -> UserError.OnSuccess[None]:
    if not re.match(r"^[\w \[\]-]{2,15}$", new_username):
        return UserError.USERNAME_RESERVED

    user = await ctx.users.find_by_id(user_id)
    if not user:
        return UserError.USER_NOT_FOUND

    if await ctx.users.username_exists(new_username):
        if user.username.lower() != new_username.lower():
            return UserError.USERNAME_TAKEN

    if await ctx.users.username_in_history(new_username):
        return UserError.USERNAME_RESERVED

    await ctx.users.update_username(user_id, new_username, user.username)
    return None


async def unlink_discord(
    ctx: AbstractContext,
    user_id: int,
) -> UserError.OnSuccess[None]:
    discord_id = await ctx.users.get_discord_id(user_id)
    if not discord_id:
        return UserError.NO_DISCORD_LINKED

    await ctx.users.unlink_discord(user_id)
    return None


async def get_email(
    ctx: AbstractContext,
    user_id: int,
) -> UserError.OnSuccess[str]:
    email = await ctx.users.get_email(user_id)
    if not email:
        return UserError.USER_NOT_FOUND

    return email


async def change_password(
    ctx: AbstractContext,
    user_id: int,
    current_password: str,
    new_password: str,
    new_email: str | None = None,
) -> UserError.OnSuccess[None]:
    password_data = await ctx.users.get_password_hash(user_id)
    if not password_data:
        return UserError.USER_NOT_FOUND

    stored_hash, version = password_data

    if version == 2:
        if not crypto.verify_password(current_password, stored_hash):
            return UserError.INVALID_PASSWORD
    else:
        md5_pass = crypto.hash_token_md5(current_password)
        if not crypto.verify_password_md5(md5_pass, stored_hash):
            return UserError.INVALID_PASSWORD

    if new_password:
        if len(new_password) < 8:
            return UserError.WEAK_PASSWORD
        new_hash = crypto.hash_password(new_password)
        await ctx.users.update_password(user_id, new_hash)

    if new_email:
        await ctx.users.update_email(user_id, new_email)

    return None


# Magic bytes for supported image formats
ALLOWED_IMAGE_MAGIC = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",  # JPEG
    b"GIF87a",  # GIF87a
    b"GIF89a",  # GIF89a
)


def _validate_image_magic(data: bytes) -> bool:
    """Check if image data starts with a valid magic byte sequence."""
    return any(data.startswith(magic) for magic in ALLOWED_IMAGE_MAGIC)


async def upload_avatar(
    ctx: AbstractContext,
    user_id: int,
    image_data: bytes,
) -> UserError.OnSuccess[str]:
    """Save user avatar image. Returns path on success."""
    if len(image_data) > settings.MAX_AVATAR_SIZE:
        return UserError.FILE_TOO_LARGE

    if not _validate_image_magic(image_data):
        return UserError.INVALID_FILE_FORMAT

    path = await ctx.user_files.save_avatar(user_id, image_data)
    if not path:
        return UserError.UPLOAD_FAILED

    return path


async def upload_banner(
    ctx: AbstractContext,
    user_id: int,
    image_data: bytes,
) -> UserError.OnSuccess[str]:
    """Save user banner image. Returns path on success."""
    if len(image_data) > settings.MAX_BANNER_SIZE:
        return UserError.FILE_TOO_LARGE

    if not _validate_image_magic(image_data):
        return UserError.INVALID_FILE_FORMAT

    path = await ctx.user_files.save_banner(user_id, image_data)
    if not path:
        return UserError.UPLOAD_FAILED

    return path


async def delete_avatar(
    ctx: AbstractContext,
    user_id: int,
) -> UserError.OnSuccess[None]:
    """Delete user avatar image."""
    await ctx.user_files.delete_avatar(user_id)
    return None


async def delete_banner(
    ctx: AbstractContext,
    user_id: int,
) -> UserError.OnSuccess[None]:
    """Delete user banner image."""
    await ctx.user_files.delete_banner(user_id)
    return None
