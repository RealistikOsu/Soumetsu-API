from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresAuth
from soumetsu_api.api.v2.context import RequiresAuthTransaction
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.constants import CustomMode
from soumetsu_api.constants import GameMode
from soumetsu_api.services import clans

router = APIRouter(prefix="/clans")


class ClanResponse(BaseModel):
    id: int
    name: str
    description: str
    icon: str
    tag: str
    member_limit: int
    member_count: int


class ClanMemberResponse(BaseModel):
    user_id: int
    username: str
    country: str
    is_owner: bool


class CreateClanRequest(BaseModel):
    name: str
    tag: str
    description: str = ""


class UpdateClanRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None


class JoinClanRequest(BaseModel):
    invite: str


class InviteResponse(BaseModel):
    invite: str


class ClanStatsResponse(BaseModel):
    total_pp: int
    average_pp: int
    total_ranked_score: int
    total_total_score: int
    total_playcount: int
    total_replays_watched: int
    total_hits: int
    rank: int


class ClanModeStatsResponse(BaseModel):
    pp: int
    ranked_score: int
    total_score: int
    playcount: int


class ClanLeaderboardEntryResponse(BaseModel):
    id: int
    name: str
    tag: str
    icon: str
    chosen_mode: ClanModeStatsResponse
    rank: int
    member_count: int


class ClanTopScoreBeatmapResponse(BaseModel):
    beatmap_id: int
    beatmapset_id: int
    song_name: str
    difficulty: float
    ranked: int


class ClanTopScoreResponse(BaseModel):
    id: int
    player_id: int
    username: str
    pp: float
    accuracy: float
    mods: int
    max_combo: int
    beatmap: ClanTopScoreBeatmapResponse


class ClanMemberLeaderboardResponse(BaseModel):
    id: int
    username: str
    country: str
    pp: int
    accuracy: float
    playcount: int
    level: float


def _to_response(c: clans.ClanResult) -> ClanResponse:
    return ClanResponse(
        id=c.id,
        name=c.name,
        description=c.description,
        icon=c.icon,
        tag=c.tag,
        member_limit=c.member_limit,
        member_count=c.member_count,
    )


def _member_to_response(m: clans.ClanMemberResult) -> ClanMemberResponse:
    return ClanMemberResponse(
        user_id=m.user_id,
        username=m.username,
        country=m.country,
        is_owner=m.is_owner,
    )


@router.get("/", response_model=response.BaseResponse[list[ClanResponse]])
async def search_clans(
    ctx: RequiresContext,
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await clans.search_clans(ctx, q, page, limit)
    result = response.unwrap(result)

    return response.create([_to_response(c) for c in result])


@router.get(
    "/leaderboard",
    response_model=response.BaseResponse[list[ClanLeaderboardEntryResponse]],
)
async def get_clan_leaderboard(
    ctx: RequiresContext,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await clans.get_clan_leaderboard(ctx, mode, custom_mode, page, limit)
    result = response.unwrap(result)

    return response.create(
        [
            ClanLeaderboardEntryResponse(
                id=e.id,
                name=e.name,
                tag=e.tag,
                icon=e.icon,
                chosen_mode=ClanModeStatsResponse(
                    pp=e.chosen_mode.pp,
                    ranked_score=e.chosen_mode.ranked_score,
                    total_score=e.chosen_mode.total_score,
                    playcount=e.chosen_mode.playcount,
                ),
                rank=e.rank,
                member_count=e.member_count,
            )
            for e in result
        ],
    )


@router.post("/", response_model=response.BaseResponse[ClanResponse])
async def create_clan(
    ctx: RequiresAuthTransaction,
    body: CreateClanRequest,
) -> Response:
    result = await clans.create_clan(
        ctx,
        ctx.user_id,
        body.name,
        body.tag,
        body.description,
    )
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.get("/{clan_id}", response_model=response.BaseResponse[ClanResponse])
async def get_clan(
    ctx: RequiresContext,
    clan_id: int,
) -> Response:
    result = await clans.get_clan(ctx, clan_id)
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.get(
    "/{clan_id}/stats",
    response_model=response.BaseResponse[ClanStatsResponse],
)
async def get_clan_stats(
    ctx: RequiresContext,
    clan_id: int,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
) -> Response:
    result = await clans.get_clan_stats(ctx, clan_id, mode, custom_mode)
    result = response.unwrap(result)

    return response.create(
        ClanStatsResponse(
            total_pp=result.total_pp,
            average_pp=result.average_pp,
            total_ranked_score=result.total_ranked_score,
            total_total_score=result.total_total_score,
            total_playcount=result.total_playcount,
            total_replays_watched=result.total_replays_watched,
            total_hits=result.total_hits,
            rank=result.rank,
        ),
    )


@router.get(
    "/{clan_id}/scores/top",
    response_model=response.BaseResponse[list[ClanTopScoreResponse]],
)
async def get_clan_top_scores(
    ctx: RequiresContext,
    clan_id: int,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
    limit: int = Query(4, ge=1, le=100),
) -> Response:
    result = await clans.get_clan_top_scores(ctx, clan_id, mode, custom_mode, limit)
    result = response.unwrap(result)

    return response.create(
        [
            ClanTopScoreResponse(
                id=s.id,
                player_id=s.player_id,
                username=s.username,
                pp=s.pp,
                accuracy=s.accuracy,
                mods=s.mods,
                max_combo=s.max_combo,
                beatmap=ClanTopScoreBeatmapResponse(
                    beatmap_id=s.beatmap_id,
                    beatmapset_id=s.beatmapset_id,
                    song_name=s.song_name,
                    difficulty=s.difficulty,
                    ranked=s.ranked,
                ),
            )
            for s in result
        ],
    )


@router.get(
    "/{clan_id}/members/leaderboard",
    response_model=response.BaseResponse[list[ClanMemberLeaderboardResponse]],
)
async def get_clan_member_leaderboard(
    ctx: RequiresContext,
    clan_id: int,
    mode: GameMode = Query(GameMode.STD),
    custom_mode: CustomMode = Query(CustomMode.VANILLA),
) -> Response:
    result = await clans.get_clan_member_leaderboard(ctx, clan_id, mode, custom_mode)
    result = response.unwrap(result)

    return response.create(
        [
            ClanMemberLeaderboardResponse(
                id=e.id,
                username=e.username,
                country=e.country,
                pp=e.pp,
                accuracy=e.accuracy,
                playcount=e.playcount,
                level=e.level,
            )
            for e in result
        ],
    )


@router.put("/{clan_id}", response_model=response.BaseResponse[ClanResponse])
async def update_clan(
    ctx: RequiresAuthTransaction,
    clan_id: int,
    body: UpdateClanRequest,
) -> Response:
    result = await clans.update_clan(
        ctx,
        ctx.user_id,
        clan_id,
        body.name,
        body.description,
        body.icon,
    )
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.delete("/{clan_id}", response_model=response.BaseResponse[None])
async def delete_clan(
    ctx: RequiresAuthTransaction,
    clan_id: int,
) -> Response:
    result = await clans.delete_clan(ctx, ctx.user_id, clan_id)
    response.unwrap(result)

    return response.create(None)


@router.get(
    "/{clan_id}/members",
    response_model=response.BaseResponse[list[ClanMemberResponse]],
)
async def get_members(
    ctx: RequiresContext,
    clan_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await clans.get_members(ctx, clan_id, page, limit)
    result = response.unwrap(result)

    return response.create([_member_to_response(m) for m in result])


@router.post("/join", response_model=response.BaseResponse[ClanResponse])
async def join_clan_by_invite(
    ctx: RequiresAuthTransaction,
    invite: str = Query(..., min_length=1),
) -> Response:
    result = await clans.join_clan(ctx, ctx.user_id, invite)
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.post("/{clan_id}/join", response_model=response.BaseResponse[ClanResponse])
async def join_clan(
    ctx: RequiresAuthTransaction,
    clan_id: int,
    body: JoinClanRequest,
) -> Response:
    result = await clans.join_clan(ctx, ctx.user_id, body.invite)
    result = response.unwrap(result)

    return response.create(_to_response(result))


@router.delete("/{clan_id}/members/me", response_model=response.BaseResponse[None])
async def leave_clan(
    ctx: RequiresAuthTransaction,
    clan_id: int,
) -> Response:
    result = await clans.leave_clan(ctx, ctx.user_id, clan_id)
    response.unwrap(result)

    return response.create(None)


@router.delete(
    "/{clan_id}/members/{user_id}",
    response_model=response.BaseResponse[None],
)
async def kick_member(
    ctx: RequiresAuthTransaction,
    clan_id: int,
    user_id: int,
) -> Response:
    result = await clans.kick_member(ctx, ctx.user_id, clan_id, user_id)
    response.unwrap(result)

    return response.create(None)


@router.get("/{clan_id}/invite", response_model=response.BaseResponse[InviteResponse])
async def get_invite(
    ctx: RequiresAuth,
    clan_id: int,
) -> Response:
    result = await clans.get_invite(ctx, ctx.user_id, clan_id)
    result = response.unwrap(result)

    return response.create(InviteResponse(invite=result))


@router.post("/{clan_id}/invite", response_model=response.BaseResponse[InviteResponse])
async def regenerate_invite(
    ctx: RequiresAuthTransaction,
    clan_id: int,
) -> Response:
    result = await clans.regenerate_invite(ctx, ctx.user_id, clan_id)
    result = response.unwrap(result)

    return response.create(InviteResponse(invite=result))
