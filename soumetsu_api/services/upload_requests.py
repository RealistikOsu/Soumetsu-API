from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal
from typing import override

from fastapi import status

from soumetsu_api.adapters import skins
from soumetsu_api.constants import STABLE_CUSTOM_MODES
from soumetsu_api.resources.upload_requests import UploadRequestData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.services.scores import ScoreWithBeatmapResult
from soumetsu_api.services.scores import score_with_beatmap_to_result
from soumetsu_api.utilities import privileges

STATUSES = ("pending", "accepted", "rejected")
type Status = Literal["pending", "accepted", "rejected"]

MAX_OPEN_PER_USER = 3
MAX_REASON_LENGTH = 1000


class UploadRequestError(ServiceError):
    REQUEST_NOT_FOUND = "request_not_found"
    SCORE_NOT_FOUND = "score_not_found"
    FORBIDDEN = "forbidden"
    TOO_MANY_OPEN = "too_many_open"
    INVALID_REQUEST = "invalid_request"
    INVALID_SKIN = "invalid_skin"
    CANNOT_VOTE = "cannot_vote"

    @override
    def service(self) -> str:
        return "upload_requests"

    @override
    def status_code(self) -> int:
        match self:
            case (
                UploadRequestError.REQUEST_NOT_FOUND
                | UploadRequestError.SCORE_NOT_FOUND
            ):
                return status.HTTP_404_NOT_FOUND
            case UploadRequestError.FORBIDDEN:
                return status.HTTP_403_FORBIDDEN
            case UploadRequestError.TOO_MANY_OPEN:
                return status.HTTP_429_TOO_MANY_REQUESTS
            case (
                UploadRequestError.INVALID_REQUEST
                | UploadRequestError.INVALID_SKIN
                | UploadRequestError.CANNOT_VOTE
            ):
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class UploadRequestResult:
    id: int
    user_id: int
    username: str
    country: str
    score_id: int
    custom_mode: int
    # None once the score is gone, for example after a wipe.
    score: ScoreWithBeatmapResult | None
    skin_url: str
    reason: str
    status: Status
    created_at: int
    up: int
    down: int
    mine: int


@dataclass
class UploadRequestPage:
    pages: int
    requests: list[UploadRequestResult]


@dataclass
class VoteResult:
    up: int
    down: int
    mine: int


def _result(
    request: UploadRequestData,
    scores: dict[tuple[int, int], ScoreWithBeatmapResult],
) -> UploadRequestResult:
    return UploadRequestResult(
        id=request.id,
        user_id=request.user_id,
        username=request.username,
        country=request.country,
        score_id=request.score_id,
        custom_mode=request.custom_mode,
        score=scores.get((request.custom_mode, request.score_id)),
        skin_url=request.skin_url,
        reason=request.reason,
        status=STATUSES[request.status],
        created_at=request.created_at,
        up=request.up,
        down=request.down,
        mine=request.mine,
    )


async def list_requests(
    ctx: AbstractContext,
    request_status: Status,
    page: int,
    limit: int,
    viewer_id: int | None,
) -> UploadRequestPage:
    code = STATUSES.index(request_status)
    requests = await ctx.upload_requests.list_by_status(
        code,
        viewer_id or 0,
        limit,
        (page - 1) * limit,
    )
    total = await ctx.upload_requests.count_by_status(code)

    scores: dict[tuple[int, int], ScoreWithBeatmapResult] = {}
    for custom_mode in STABLE_CUSTOM_MODES:
        ids = [r.score_id for r in requests if r.custom_mode == custom_mode]
        if not ids:
            continue
        for score in await ctx.scores.list_with_beatmap(ids, custom_mode):
            scores[(custom_mode, score.id)] = score_with_beatmap_to_result(score)

    return UploadRequestPage(
        pages=-(-total // limit),
        requests=[_result(r, scores) for r in requests],
    )


async def create_request(
    ctx: AbstractContext,
    user_id: int,
    user_privileges: int,
    score_id: int,
    skin_url: str,
    reason: str,
) -> UploadRequestError.OnSuccess[None]:
    skin_url = skin_url.strip()
    reason = reason.strip()
    if not reason or len(reason) > MAX_REASON_LENGTH:
        return UploadRequestError.INVALID_REQUEST

    if privileges.is_restricted(privileges.UserPrivileges(user_privileges)):
        return UploadRequestError.FORBIDDEN

    # Score IDs are only unique per table, so the player's own scores decide which one is meant.
    found = None
    for custom_mode in STABLE_CUSTOM_MODES:
        score = await ctx.scores.find_by_id(score_id, custom_mode)
        if score and score.player_id == user_id and score.completed >= 1:
            found = custom_mode
            break
    if found is None:
        return UploadRequestError.SCORE_NOT_FOUND

    if await ctx.upload_requests.count_open_for_user(user_id) >= MAX_OPEN_PER_USER:
        return UploadRequestError.TOO_MANY_OPEN

    if skin_url and not await skins.is_valid_skin_url(skin_url):
        return UploadRequestError.INVALID_SKIN

    await ctx.upload_requests.create(
        user_id,
        score_id,
        found,
        skin_url,
        reason,
        int(time.time()),
    )
    return None


async def withdraw_request(
    ctx: AbstractContext,
    user_id: int,
    request_id: int,
) -> UploadRequestError.OnSuccess[None]:
    found = await ctx.upload_requests.find_owner_and_status(request_id)
    if not found or found[0] != user_id or found[1] != 0:
        return UploadRequestError.REQUEST_NOT_FOUND

    await ctx.upload_requests.delete(request_id)
    return None


# A vote of 0 takes the player's vote back. Only open requests can be voted on, and not your own.
async def vote(
    ctx: AbstractContext,
    user_id: int,
    request_id: int,
    value: int,
) -> UploadRequestError.OnSuccess[VoteResult]:
    found = await ctx.upload_requests.find_owner_and_status(request_id)
    if not found:
        return UploadRequestError.REQUEST_NOT_FOUND

    owner_id, request_status = found
    if request_status != 0 or owner_id == user_id:
        return UploadRequestError.CANNOT_VOTE

    if value == 0:
        await ctx.upload_requests.clear_vote(request_id, user_id)
    else:
        await ctx.upload_requests.set_vote(request_id, user_id, value)

    up, down = await ctx.upload_requests.vote_counts(request_id)
    return VoteResult(up=up, down=down, mine=value)


async def review_request(
    ctx: AbstractContext,
    staff_id: int,
    staff_privileges: int,
    request_id: int,
    new_status: Status,
) -> UploadRequestError.OnSuccess[None]:
    if not privileges.has_privilege(
        staff_privileges,
        privileges.UserPrivileges.ADMIN_ACCESS_RAP,
    ):
        return UploadRequestError.FORBIDDEN

    if not await ctx.upload_requests.find_owner_and_status(request_id):
        return UploadRequestError.REQUEST_NOT_FOUND

    open_again = new_status == "pending"
    await ctx.upload_requests.set_status(
        request_id,
        STATUSES.index(new_status),
        None if open_again else staff_id,
        None if open_again else int(time.time()),
    )
    await ctx.admin.create_rap_log(
        staff_id,
        f"has set upload request #{request_id} to {new_status}",
        "soumetsu-api",
    )
    return None
