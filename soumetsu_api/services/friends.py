from __future__ import annotations

from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.resources.friends import FriendData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import privileges


class FriendError(ServiceError):
    USER_NOT_FOUND = "user_not_found"
    USER_RESTRICTED = "user_restricted"
    ALREADY_FRIENDS = "already_friends"
    NOT_FRIENDS = "not_friends"
    CANNOT_ADD_SELF = "cannot_add_self"

    @override
    def service(self) -> str:
        return "friends"

    @override
    def status_code(self) -> int:
        match self:
            case FriendError.USER_NOT_FOUND | FriendError.NOT_FRIENDS:
                return status.HTTP_404_NOT_FOUND
            case FriendError.USER_RESTRICTED:
                return status.HTTP_403_FORBIDDEN
            case FriendError.ALREADY_FRIENDS:
                return status.HTTP_409_CONFLICT
            case FriendError.CANNOT_ADD_SELF:
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class FriendResult:
    user_id: int
    username: str
    country: str


@dataclass
class RelationshipsResult:
    friends: list[FriendResult]
    followers: list[FriendResult]
    mutual: list[int]


def _friend_to_result(f: FriendData) -> FriendResult:
    return FriendResult(
        user_id=f.user_id,
        username=f.username,
        country=f.country,
    )


async def get_friends(
    ctx: AbstractContext,
    user_id: int,
    page: int = 1,
    limit: int = 50,
) -> FriendError.OnSuccess[list[FriendResult]]:
    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    friends = await ctx.friends.get_friends(user_id, limit, offset)
    return [_friend_to_result(f) for f in friends]


async def get_followers(
    ctx: AbstractContext,
    user_id: int,
    page: int = 1,
    limit: int = 50,
) -> FriendError.OnSuccess[list[FriendResult]]:
    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    followers = await ctx.friends.get_followers(user_id, limit, offset)
    return [_friend_to_result(f) for f in followers]


async def add_friend(
    ctx: AbstractContext,
    user_id: int,
    friend_id: int,
) -> FriendError.OnSuccess[None]:
    if user_id == friend_id:
        return FriendError.CANNOT_ADD_SELF

    user = await ctx.users.find_by_id(friend_id)
    if not user:
        return FriendError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return FriendError.USER_RESTRICTED

    if await ctx.friends.is_friend(user_id, friend_id):
        return FriendError.ALREADY_FRIENDS

    await ctx.friends.add_friend(user_id, friend_id)
    return None


async def remove_friend(
    ctx: AbstractContext,
    user_id: int,
    friend_id: int,
) -> FriendError.OnSuccess[None]:
    if not await ctx.friends.is_friend(user_id, friend_id):
        return FriendError.NOT_FRIENDS

    await ctx.friends.remove_friend(user_id, friend_id)
    return None


async def is_friend(
    ctx: AbstractContext,
    user_id: int,
    friend_id: int,
) -> FriendError.OnSuccess[bool]:
    return await ctx.friends.is_friend(user_id, friend_id)


async def get_relationships(
    ctx: AbstractContext,
    user_id: int,
    page: int = 1,
    limit: int = 50,
) -> FriendError.OnSuccess[RelationshipsResult]:
    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    friends = await ctx.friends.get_friends(user_id, limit, offset)
    followers = await ctx.friends.get_followers(user_id, limit, offset)

    mutual_ids = []
    for f in friends:
        if await ctx.friends.is_mutual(user_id, f.user_id):
            mutual_ids.append(f.user_id)

    return RelationshipsResult(
        friends=[_friend_to_result(f) for f in friends],
        followers=[_friend_to_result(f) for f in followers],
        mutual=mutual_ids,
    )


@dataclass
class FollowerStatsResult:
    follower_count: int
    friend_count: int


async def get_follower_stats(
    ctx: AbstractContext,
    user_id: int,
) -> FriendError.OnSuccess[FollowerStatsResult]:
    follower_count = await ctx.friends.get_follower_count(user_id)
    friend_count = await ctx.friends.get_friend_count(user_id)

    return FollowerStatsResult(
        follower_count=follower_count,
        friend_count=friend_count,
    )
