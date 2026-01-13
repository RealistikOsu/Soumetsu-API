from __future__ import annotations

import time
from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.resources.comments import CommentData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import privileges


class CommentError(ServiceError):
    COMMENT_NOT_FOUND = "comment_not_found"
    USER_NOT_FOUND = "user_not_found"
    FORBIDDEN = "forbidden"
    COMMENTS_DISABLED = "comments_disabled"

    @override
    def service(self) -> str:
        return "comments"

    @override
    def status_code(self) -> int:
        match self:
            case CommentError.COMMENT_NOT_FOUND | CommentError.USER_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case CommentError.FORBIDDEN | CommentError.COMMENTS_DISABLED:
                return status.HTTP_403_FORBIDDEN
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class CommentResult:
    id: int
    author_id: int
    author_username: str
    profile_id: int
    message: str
    created_at: int


def _comment_to_result(c: CommentData) -> CommentResult:
    return CommentResult(
        id=c.id,
        author_id=c.author_id,
        author_username=c.author_username,
        profile_id=c.profile_id,
        message=c.message,
        created_at=int(c.created_at) if c.created_at else 0,
    )


async def get_comment(
    ctx: AbstractContext,
    comment_id: int,
) -> CommentError.OnSuccess[CommentResult]:
    comment = await ctx.comments.find_by_id(comment_id)
    if not comment:
        return CommentError.COMMENT_NOT_FOUND

    return _comment_to_result(comment)


async def list_profile_comments(
    ctx: AbstractContext,
    profile_id: int,
    page: int = 1,
    limit: int = 50,
) -> CommentError.OnSuccess[list[CommentResult]]:
    user = await ctx.users.find_by_id(profile_id)
    if not user:
        return CommentError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return CommentError.USER_NOT_FOUND

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    comments = await ctx.comments.list_for_profile(profile_id, limit, offset)
    return [_comment_to_result(c) for c in comments]


async def create_comment(
    ctx: AbstractContext,
    author_id: int,
    profile_id: int,
    message: str,
) -> CommentError.OnSuccess[CommentResult]:
    user = await ctx.users.find_by_id(profile_id)
    if not user:
        return CommentError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return CommentError.USER_NOT_FOUND

    created_at = str(int(time.time()))
    comment_id = await ctx.comments.create(
        author_id=author_id,
        profile_id=profile_id,
        message=message,
        created_at=created_at,
    )

    comment = await ctx.comments.find_by_id(comment_id)
    if not comment:
        return CommentError.COMMENT_NOT_FOUND

    return _comment_to_result(comment)


async def delete_comment(
    ctx: AbstractContext,
    user_id: int,
    comment_id: int,
    is_admin: bool = False,
) -> CommentError.OnSuccess[None]:
    author_id = await ctx.comments.find_author_id(comment_id)
    if author_id is None:
        return CommentError.COMMENT_NOT_FOUND

    if author_id != user_id and not is_admin:
        return CommentError.FORBIDDEN

    await ctx.comments.delete(comment_id)
    return None
