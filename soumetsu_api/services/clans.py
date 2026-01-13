from __future__ import annotations

from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.resources.clans import CLAN_PERM_MEMBER
from soumetsu_api.resources.clans import CLAN_PERM_OWNER
from soumetsu_api.resources.clans import ClanData
from soumetsu_api.resources.clans import ClanMemberData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import crypto


class ClanError(ServiceError):
    CLAN_NOT_FOUND = "clan_not_found"
    NOT_OWNER = "not_owner"
    NOT_MEMBER = "not_member"
    ALREADY_IN_CLAN = "already_in_clan"
    CLAN_FULL = "clan_full"
    INVALID_INVITE = "invalid_invite"
    NAME_TAKEN = "name_taken"
    TAG_TAKEN = "tag_taken"
    CANNOT_KICK_OWNER = "cannot_kick_owner"
    USER_NOT_IN_CLAN = "user_not_in_clan"

    @override
    def service(self) -> str:
        return "clans"

    @override
    def status_code(self) -> int:
        match self:
            case ClanError.CLAN_NOT_FOUND | ClanError.USER_NOT_IN_CLAN:
                return status.HTTP_404_NOT_FOUND
            case (
                ClanError.NOT_OWNER | ClanError.NOT_MEMBER | ClanError.CANNOT_KICK_OWNER
            ):
                return status.HTTP_403_FORBIDDEN
            case (
                ClanError.ALREADY_IN_CLAN
                | ClanError.CLAN_FULL
                | ClanError.NAME_TAKEN
                | ClanError.TAG_TAKEN
            ):
                return status.HTTP_409_CONFLICT
            case ClanError.INVALID_INVITE:
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class ClanResult:
    id: int
    name: str
    description: str
    icon: str
    tag: str
    member_limit: int
    member_count: int


@dataclass
class ClanMemberResult:
    user_id: int
    username: str
    country: str
    is_owner: bool


def _clan_to_result(c: ClanData, member_count: int) -> ClanResult:
    return ClanResult(
        id=c.id,
        name=c.name,
        description=c.description,
        icon=c.icon,
        tag=c.tag,
        member_limit=c.member_limit,
        member_count=member_count,
    )


def _member_to_result(m: ClanMemberData) -> ClanMemberResult:
    return ClanMemberResult(
        user_id=m.user_id,
        username=m.username,
        country=m.country,
        is_owner=m.perms == CLAN_PERM_OWNER,
    )


async def get_clan(
    ctx: AbstractContext,
    clan_id: int,
) -> ClanError.OnSuccess[ClanResult]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    member_count = await ctx.clans.get_member_count(clan_id)
    return _clan_to_result(clan, member_count)


async def search_clans(
    ctx: AbstractContext,
    query: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> ClanError.OnSuccess[list[ClanResult]]:
    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    clans = await ctx.clans.search(query, limit, offset)
    results = []
    for c in clans:
        member_count = await ctx.clans.get_member_count(c.id)
        results.append(_clan_to_result(c, member_count))

    return results


async def create_clan(
    ctx: AbstractContext,
    user_id: int,
    name: str,
    tag: str,
    description: str = "",
) -> ClanError.OnSuccess[ClanResult]:
    if await ctx.clans.get_user_clan(user_id):
        return ClanError.ALREADY_IN_CLAN

    if await ctx.clans.name_exists(name):
        return ClanError.NAME_TAKEN

    if await ctx.clans.tag_exists(tag):
        return ClanError.TAG_TAKEN

    clan_id = await ctx.clans.create(name, description, tag)
    await ctx.clans.add_member(clan_id, user_id, CLAN_PERM_OWNER)

    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    return _clan_to_result(clan, 1)


async def update_clan(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
    name: str | None = None,
    description: str | None = None,
    icon: str | None = None,
) -> ClanError.OnSuccess[ClanResult]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    if name and name != clan.name:
        if await ctx.clans.name_exists(name):
            return ClanError.NAME_TAKEN

    await ctx.clans.update(clan_id, name, description, icon)

    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    member_count = await ctx.clans.get_member_count(clan_id)
    return _clan_to_result(clan, member_count)


async def delete_clan(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
) -> ClanError.OnSuccess[None]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    await ctx.clans.delete(clan_id)
    return None


async def get_members(
    ctx: AbstractContext,
    clan_id: int,
    page: int = 1,
    limit: int = 50,
) -> ClanError.OnSuccess[list[ClanMemberResult]]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    members = await ctx.clans.get_members(clan_id, limit, offset)
    return [_member_to_result(m) for m in members]


async def join_clan(
    ctx: AbstractContext,
    user_id: int,
    invite: str,
) -> ClanError.OnSuccess[ClanResult]:
    if await ctx.clans.get_user_clan(user_id):
        return ClanError.ALREADY_IN_CLAN

    clan_id = await ctx.clans.get_clan_by_invite(invite)
    if not clan_id:
        return ClanError.INVALID_INVITE

    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    member_count = await ctx.clans.get_member_count(clan_id)
    if member_count >= clan.member_limit:
        return ClanError.CLAN_FULL

    await ctx.clans.add_member(clan_id, user_id, CLAN_PERM_MEMBER)

    return _clan_to_result(clan, member_count + 1)


async def leave_clan(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
) -> ClanError.OnSuccess[None]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms is None:
        return ClanError.NOT_MEMBER

    if perms == CLAN_PERM_OWNER:
        await ctx.clans.delete(clan_id)
    else:
        await ctx.clans.remove_member(clan_id, user_id)

    return None


async def kick_member(
    ctx: AbstractContext,
    owner_id: int,
    clan_id: int,
    user_id: int,
) -> ClanError.OnSuccess[None]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    owner_perms = await ctx.clans.get_user_perms(owner_id, clan_id)
    if owner_perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    user_perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if user_perms is None:
        return ClanError.USER_NOT_IN_CLAN

    if user_perms == CLAN_PERM_OWNER:
        return ClanError.CANNOT_KICK_OWNER

    await ctx.clans.remove_member(clan_id, user_id)
    return None


async def get_invite(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
) -> ClanError.OnSuccess[str]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    invite = await ctx.clans.get_invite(clan_id)
    if not invite:
        invite = crypto.generate_token(8)
        await ctx.clans.set_invite(clan_id, invite)

    return invite


async def regenerate_invite(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
) -> ClanError.OnSuccess[str]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    invite = crypto.generate_token(8)
    await ctx.clans.set_invite(clan_id, invite)

    return invite
