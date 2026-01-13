from __future__ import annotations

from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError


class BadgeError(ServiceError):
    BADGE_NOT_FOUND = "badge_not_found"

    @override
    def service(self) -> str:
        return "badges"

    @override
    def status_code(self) -> int:
        match self:
            case BadgeError.BADGE_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class BadgeResult:
    id: int
    name: str
    icon: str


@dataclass
class BadgeMemberResult:
    user_id: int
    username: str
    country: str


async def get_badge(
    ctx: AbstractContext,
    badge_id: int,
) -> BadgeError.OnSuccess[BadgeResult]:
    badge = await ctx.badges.get_by_id(badge_id)
    if not badge:
        return BadgeError.BADGE_NOT_FOUND

    return BadgeResult(
        id=badge.id,
        name=badge.name,
        icon=badge.icon,
    )


async def get_badges(
    ctx: AbstractContext,
    page: int = 1,
    limit: int = 50,
) -> BadgeError.OnSuccess[list[BadgeResult]]:
    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    badges = await ctx.badges.get_all(limit, offset)

    return [
        BadgeResult(id=b.id, name=b.name, icon=b.icon)
        for b in badges
    ]


async def get_badge_members(
    ctx: AbstractContext,
    badge_id: int,
    page: int = 1,
    limit: int = 50,
) -> BadgeError.OnSuccess[list[BadgeMemberResult]]:
    badge = await ctx.badges.get_by_id(badge_id)
    if not badge:
        return BadgeError.BADGE_NOT_FOUND

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    members = await ctx.badges.get_members(badge_id, limit, offset)

    return [
        BadgeMemberResult(
            user_id=m.user_id,
            username=m.username,
            country=m.country,
        )
        for m in members
    ]
