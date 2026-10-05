from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel
from pydantic import Field

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import OptionalAuth
from soumetsu_api.api.v2.context import RequiresAuthTransaction
from soumetsu_api.api.v2.scores import ScoreWithBeatmapResponse
from soumetsu_api.api.v2.scores import to_response as score_response
from soumetsu_api.services import upload_requests

router = APIRouter(prefix="/upload-requests")


class UploadRequestPlayer(BaseModel):
    id: int
    username: str
    country: str


class UploadRequestResponse(BaseModel):
    id: int
    user: UploadRequestPlayer
    score_id: int
    custom_mode: int
    score: ScoreWithBeatmapResponse | None
    skin_url: str
    reason: str
    status: Literal["pending", "accepted", "rejected"]
    created_at: int
    up: int
    down: int
    # The viewer's own vote: 1, -1, or 0 for none.
    mine: int


class UploadRequestPageResponse(BaseModel):
    pages: int
    requests: list[UploadRequestResponse]


class CreateUploadRequest(BaseModel):
    score_id: int = Field(ge=1)
    skin_url: str = ""
    reason: str


class VoteRequest(BaseModel):
    vote: Literal[-1, 0, 1]


class VoteResponse(BaseModel):
    up: int
    down: int
    mine: int


class ReviewRequest(BaseModel):
    status: Literal["pending", "accepted", "rejected"]


def _to_response(r: upload_requests.UploadRequestResult) -> UploadRequestResponse:
    return UploadRequestResponse(
        id=r.id,
        user=UploadRequestPlayer(id=r.user_id, username=r.username, country=r.country),
        score_id=r.score_id,
        custom_mode=r.custom_mode,
        score=score_response(r.score) if r.score else None,
        skin_url=r.skin_url,
        reason=r.reason,
        status=r.status,
        created_at=r.created_at,
        up=r.up,
        down=r.down,
        mine=r.mine,
    )


@router.get("/", response_model=response.BaseResponse[UploadRequestPageResponse])
async def list_upload_requests(
    ctx: OptionalAuth,
    status: Literal["pending", "accepted", "rejected"] = Query("pending"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
) -> Response:
    result = await upload_requests.list_requests(
        ctx,
        status,
        page,
        limit,
        ctx.session.user_id if ctx.session else None,
    )

    return response.create(
        UploadRequestPageResponse(
            pages=result.pages,
            requests=[_to_response(r) for r in result.requests],
        ),
    )


@router.post("/", response_model=response.BaseResponse[None])
async def create_upload_request(
    ctx: RequiresAuthTransaction,
    body: CreateUploadRequest,
) -> Response:
    result = await upload_requests.create_request(
        ctx,
        ctx.user_id,
        ctx.privileges,
        body.score_id,
        body.skin_url,
        body.reason,
    )
    response.unwrap(result)

    return response.create(None)


@router.delete("/{request_id}", response_model=response.BaseResponse[None])
async def withdraw_upload_request(
    ctx: RequiresAuthTransaction,
    request_id: int,
) -> Response:
    result = await upload_requests.withdraw_request(ctx, ctx.user_id, request_id)
    response.unwrap(result)

    return response.create(None)


@router.put("/{request_id}/vote", response_model=response.BaseResponse[VoteResponse])
async def vote_upload_request(
    ctx: RequiresAuthTransaction,
    request_id: int,
    body: VoteRequest,
) -> Response:
    result = await upload_requests.vote(ctx, ctx.user_id, request_id, body.vote)
    result = response.unwrap(result)

    return response.create(
        VoteResponse(up=result.up, down=result.down, mine=result.mine),
    )


@router.put("/{request_id}/status", response_model=response.BaseResponse[None])
async def review_upload_request(
    ctx: RequiresAuthTransaction,
    request_id: int,
    body: ReviewRequest,
) -> Response:
    result = await upload_requests.review_request(
        ctx,
        ctx.user_id,
        ctx.privileges,
        request_id,
        body.status,
    )
    response.unwrap(result)

    return response.create(None)
