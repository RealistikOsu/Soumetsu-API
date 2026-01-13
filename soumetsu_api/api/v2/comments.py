from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresAuthTransaction
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import comments
from soumetsu_api.utilities import privileges

router = APIRouter(prefix="/comments")


class CommentResponse(BaseModel):
    id: int
    author_id: int
    author_username: str
    profile_id: int
    message: str
    created_at: str


class CreateCommentRequest(BaseModel):
    target_id: int
    content: str


def _to_response(c: comments.CommentResult) -> CommentResponse:
    return CommentResponse(
        id=c.id,
        author_id=c.author_id,
        author_username=c.author_username,
        profile_id=c.profile_id,
        message=c.message,
        created_at=c.created_at,
    )


@router.get("/{comment_id}", response_model=response.BaseResponse[CommentResponse])
async def get_comment(
    ctx: RequiresContext,
    comment_id: int,
) -> Response:
    result = await comments.get_comment(ctx, comment_id)
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.post("/", response_model=response.BaseResponse[CommentResponse])
async def create_comment(
    ctx: RequiresAuthTransaction,
    body: CreateCommentRequest,
) -> Response:
    result = await comments.create_comment(
        ctx,
        ctx.user_id,
        body.target_id,
        body.content,
    )
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.delete("/{comment_id}", response_model=response.BaseResponse[None])
async def delete_comment(
    ctx: RequiresAuthTransaction,
    comment_id: int,
) -> Response:
    is_admin = privileges.has_privilege(
        privileges.UserPrivileges(ctx.privileges),
        privileges.UserPrivileges.ADMIN_MANAGE_USERS,
    )

    result = await comments.delete_comment(
        ctx,
        ctx.user_id,
        comment_id,
        is_admin,
    )
    response.unwrap(result)

    return response.create(None)


@router.get(
    "/users/{user_id}",
    response_model=response.BaseResponse[list[CommentResponse]],
)
async def get_user_comments(
    ctx: RequiresContext,
    user_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await comments.get_user_comments(ctx, user_id, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(c) for c in result])
