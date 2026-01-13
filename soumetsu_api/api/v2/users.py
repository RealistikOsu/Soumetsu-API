from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from fastapi import UploadFile
from fastapi import status
from pydantic import BaseModel

from soumetsu_api.adapters import storage
from soumetsu_api.api.v2 import response
from soumetsu_api.api.v2.context import RequiresAuth
from soumetsu_api.api.v2.context import RequiresAuthTransaction
from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.services import achievements
from soumetsu_api.services import beatmaps
from soumetsu_api.services import comments
from soumetsu_api.services import friends
from soumetsu_api.services import user_history
from soumetsu_api.services import users

router = APIRouter(prefix="/users")


class ClanInfoResponse(BaseModel):
    id: int
    name: str
    tag: str


class UserStatsResponse(BaseModel):
    mode: int
    playstyle: int
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


class UserProfileResponse(BaseModel):
    id: int
    username: str
    country: str
    privileges: int
    registered_at: int
    latest_activity: int
    is_online: bool
    clan: ClanInfoResponse | None
    stats: UserStatsResponse


class UserCompactResponse(BaseModel):
    id: int
    username: str
    country: str
    privileges: int


class UserCardResponse(BaseModel):
    """Minimal user info for hover cards - optimized payload size."""

    id: int
    username: str
    country: str
    privileges: int
    global_rank: int
    country_rank: int
    is_online: bool


class UserSettingsResponse(BaseModel):
    username_aka: str
    favourite_mode: int
    prefer_relax: int
    play_style: int
    show_country: bool


class UpdateSettingsRequest(BaseModel):
    username_aka: str | None = None
    favourite_mode: int | None = None
    prefer_relax: int | None = None
    play_style: int | None = None
    show_country: bool | None = None


class UserpageResponse(BaseModel):
    content: str


class UpdateUserpageRequest(BaseModel):
    content: str


class ChangeUsernameRequest(BaseModel):
    username: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str | None = None
    new_email: str | None = None


class EmailResponse(BaseModel):
    email: str


@router.get("/search", response_model=response.BaseResponse[list[UserCompactResponse]])
async def search_users(
    ctx: RequiresContext,
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await users.search_users(ctx, q, page, limit)
    result = response.unwrap(result)

    return response.create(
        [
            UserCompactResponse(
                id=u.id,
                username=u.username,
                country=u.country,
                privileges=u.privileges,
            )
            for u in result
        ],
    )


@router.get("/resolve", response_model=response.BaseResponse[int])
async def resolve_username(
    ctx: RequiresContext,
    username: str = Query(..., min_length=1),
) -> Response:
    result = await users.resolve_username(ctx, username)
    result = response.unwrap(result)

    return response.create(result)


@router.get("/me", response_model=response.BaseResponse[UserProfileResponse])
async def get_me(
    ctx: RequiresAuth,
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
) -> Response:
    result = await users.get_profile(ctx, ctx.user_id, mode, playstyle)
    result = response.unwrap(result)

    clan = None
    if result.clan:
        clan = ClanInfoResponse(
            id=result.clan.id,
            name=result.clan.name,
            tag=result.clan.tag,
        )

    return response.create(
        UserProfileResponse(
            id=result.id,
            username=result.username,
            country=result.country,
            privileges=result.privileges,
            registered_at=result.registered_at,
            latest_activity=result.latest_activity,
            is_online=result.is_online,
            clan=clan,
            stats=UserStatsResponse(
                mode=result.stats.mode,
                playstyle=result.stats.playstyle,
                global_rank=result.stats.global_rank,
                country_rank=result.stats.country_rank,
                pp=result.stats.pp,
                accuracy=result.stats.accuracy,
                playcount=result.stats.playcount,
                total_score=result.stats.total_score,
                ranked_score=result.stats.ranked_score,
                total_hits=result.stats.total_hits,
                playtime=result.stats.playtime,
                max_combo=result.stats.max_combo,
                replays_watched=result.stats.replays_watched,
                level=result.stats.level,
                first_places=result.stats.first_places,
            ),
        ),
    )


@router.get("/me/settings", response_model=response.BaseResponse[UserSettingsResponse])
async def get_settings(ctx: RequiresAuth) -> Response:
    result = await users.get_settings(ctx, ctx.user_id)
    result = response.unwrap(result)

    return response.create(
        UserSettingsResponse(
            username_aka=result.username_aka,
            favourite_mode=result.favourite_mode,
            prefer_relax=result.prefer_relax,
            play_style=result.play_style,
            show_country=result.show_country,
        ),
    )


@router.put("/me/settings", response_model=response.BaseResponse[None])
async def update_settings(
    ctx: RequiresAuthTransaction,
    body: UpdateSettingsRequest,
) -> Response:
    result = await users.update_settings(
        ctx,
        ctx.user_id,
        username_aka=body.username_aka,
        favourite_mode=body.favourite_mode,
        prefer_relax=body.prefer_relax,
        play_style=body.play_style,
        show_country=body.show_country,
    )
    response.unwrap(result)

    return response.create(None)


@router.get("/me/userpage", response_model=response.BaseResponse[UserpageResponse])
async def get_my_userpage(ctx: RequiresAuth) -> Response:
    result = await users.get_userpage(ctx, ctx.user_id)
    result = response.unwrap(result)

    return response.create(UserpageResponse(content=result))


@router.put("/me/userpage", response_model=response.BaseResponse[None])
async def update_my_userpage(
    ctx: RequiresAuthTransaction,
    body: UpdateUserpageRequest,
) -> Response:
    result = await users.update_userpage(ctx, ctx.user_id, body.content)
    response.unwrap(result)

    return response.create(None)


@router.put("/me/username", response_model=response.BaseResponse[None])
async def change_username(
    ctx: RequiresAuthTransaction,
    body: ChangeUsernameRequest,
) -> Response:
    result = await users.change_username(ctx, ctx.user_id, body.username)
    response.unwrap(result)

    return response.create(None)


@router.delete("/me/discord", response_model=response.BaseResponse[None])
async def unlink_discord(ctx: RequiresAuthTransaction) -> Response:
    result = await users.unlink_discord(ctx, ctx.user_id)
    response.unwrap(result)

    return response.create(None)


@router.get("/me/email", response_model=response.BaseResponse[EmailResponse])
async def get_email(ctx: RequiresAuth) -> Response:
    result = await users.get_email(ctx, ctx.user_id)
    result = response.unwrap(result)

    return response.create(EmailResponse(email=result))


@router.put("/me/password", response_model=response.BaseResponse[None])
async def change_password(
    ctx: RequiresAuthTransaction,
    body: ChangePasswordRequest,
) -> Response:
    result = await users.change_password(
        ctx,
        ctx.user_id,
        body.current_password,
        body.new_password or "",
        body.new_email,
    )
    response.unwrap(result)

    return response.create(None)


class UploadResponse(BaseModel):
    path: str


MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/me/avatar", response_model=response.BaseResponse[UploadResponse])
async def upload_avatar(ctx: RequiresAuth, file: UploadFile) -> Response:
    if not file.content_type or not file.content_type.startswith("image/"):
        return response.create(
            data="users.invalid_image_type",
            status=status.HTTP_400_BAD_REQUEST,
        )

    image_data = await file.read()
    if len(image_data) > MAX_IMAGE_SIZE:
        return response.create(
            data="users.image_too_large",
            status=status.HTTP_400_BAD_REQUEST,
        )

    path = await storage.save_avatar(ctx.user_id, image_data)
    if not path:
        return response.create(
            data="users.image_processing_failed",
            status=status.HTTP_400_BAD_REQUEST,
        )

    return response.create(UploadResponse(path=path))


@router.delete("/me/avatar", response_model=response.BaseResponse[None])
async def delete_avatar(ctx: RequiresAuth) -> Response:
    await storage.delete_avatar(ctx.user_id)
    return response.create(None)


@router.post("/me/banner", response_model=response.BaseResponse[UploadResponse])
async def upload_banner(ctx: RequiresAuth, file: UploadFile) -> Response:
    if not file.content_type or not file.content_type.startswith("image/"):
        return response.create(
            data="users.invalid_image_type",
            status=status.HTTP_400_BAD_REQUEST,
        )

    image_data = await file.read()
    if len(image_data) > MAX_IMAGE_SIZE:
        return response.create(
            data="users.image_too_large",
            status=status.HTTP_400_BAD_REQUEST,
        )

    path = await storage.save_banner(ctx.user_id, image_data)
    if not path:
        return response.create(
            data="users.image_processing_failed",
            status=status.HTTP_400_BAD_REQUEST,
        )

    return response.create(UploadResponse(path=path))


@router.delete("/me/banner", response_model=response.BaseResponse[None])
async def delete_banner(ctx: RequiresAuth) -> Response:
    await storage.delete_banner(ctx.user_id)
    return response.create(None)


@router.get("/{user_id}/card", response_model=response.BaseResponse[UserCardResponse])
async def get_user_card(
    ctx: RequiresContext,
    user_id: int,
) -> Response:
    """Get minimal user info for hover cards. Optimized for fast loading."""
    result = await users.get_card(ctx, user_id)
    result = response.unwrap(result)

    return response.create(
        UserCardResponse(
            id=result.id,
            username=result.username,
            country=result.country,
            privileges=result.privileges,
            global_rank=result.global_rank,
            country_rank=result.country_rank,
            is_online=result.is_online,
        ),
    )


@router.get("/{user_id}", response_model=response.BaseResponse[UserProfileResponse])
async def get_user(
    ctx: RequiresContext,
    user_id: int,
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
) -> Response:
    result = await users.get_profile(ctx, user_id, mode, playstyle)
    result = response.unwrap(result)

    clan = None
    if result.clan:
        clan = ClanInfoResponse(
            id=result.clan.id,
            name=result.clan.name,
            tag=result.clan.tag,
        )

    return response.create(
        UserProfileResponse(
            id=result.id,
            username=result.username,
            country=result.country,
            privileges=result.privileges,
            registered_at=result.registered_at,
            latest_activity=result.latest_activity,
            is_online=result.is_online,
            clan=clan,
            stats=UserStatsResponse(
                mode=result.stats.mode,
                playstyle=result.stats.playstyle,
                global_rank=result.stats.global_rank,
                country_rank=result.stats.country_rank,
                pp=result.stats.pp,
                accuracy=result.stats.accuracy,
                playcount=result.stats.playcount,
                total_score=result.stats.total_score,
                ranked_score=result.stats.ranked_score,
                total_hits=result.stats.total_hits,
                playtime=result.stats.playtime,
                max_combo=result.stats.max_combo,
                replays_watched=result.stats.replays_watched,
                level=result.stats.level,
                first_places=result.stats.first_places,
            ),
        ),
    )


@router.get(
    "/{user_id}/userpage",
    response_model=response.BaseResponse[UserpageResponse],
)
async def get_userpage(
    ctx: RequiresContext,
    user_id: int,
) -> Response:
    result = await users.get_userpage(ctx, user_id)
    result = response.unwrap(result)

    return response.create(UserpageResponse(content=result))


class CommentResponse(BaseModel):
    id: int
    author_id: int
    author_username: str
    profile_id: int
    message: str
    created_at: int


@router.get(
    "/{user_id}/comments",
    response_model=response.BaseResponse[list[CommentResponse]],
)
async def list_profile_comments(
    ctx: RequiresContext,
    user_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
) -> Response:
    result = await comments.list_profile_comments(ctx, user_id, page, limit)
    result = response.unwrap(result)

    return response.create(
        [
            CommentResponse(
                id=c.id,
                author_id=c.author_id,
                author_username=c.author_username,
                profile_id=c.profile_id,
                message=c.message,
                created_at=c.created_at,
            )
            for c in result
        ],
    )


class FollowerStatsResponse(BaseModel):
    follower_count: int
    friend_count: int


@router.get(
    "/{user_id}/followers",
    response_model=response.BaseResponse[FollowerStatsResponse],
)
async def get_user_followers(
    ctx: RequiresContext,
    user_id: int,
) -> Response:
    result = await friends.get_follower_stats(ctx, user_id)
    result = response.unwrap(result)

    return response.create(
        FollowerStatsResponse(
            follower_count=result.follower_count,
            friend_count=result.friend_count,
        ),
    )


class AchievementResponse(BaseModel):
    id: int
    name: str
    description: str
    file: str
    achieved: bool
    achieved_at: int | None


@router.get(
    "/{user_id}/achievements",
    response_model=response.BaseResponse[list[AchievementResponse]],
)
async def get_user_achievements(
    ctx: RequiresContext,
    user_id: int,
) -> Response:
    result = await achievements.get_user_achievements(ctx, user_id)
    result = response.unwrap(result)

    return response.create(
        [
            AchievementResponse(
                id=a.id,
                name=a.name,
                description=a.description,
                file=a.file,
                achieved=a.achieved,
                achieved_at=a.achieved_at,
            )
            for a in result
        ],
    )


class RankHistoryResponse(BaseModel):
    overall: int
    country: int | None
    captured_at: str


class PPHistoryResponse(BaseModel):
    pp: int | None
    captured_at: str


@router.get(
    "/{user_id}/history/rank",
    response_model=response.BaseResponse[list[RankHistoryResponse]],
)
async def get_user_rank_history(
    ctx: RequiresContext,
    user_id: int,
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
) -> Response:
    result = await user_history.get_rank_history(ctx, user_id, mode, playstyle)
    result = response.unwrap(result)

    return response.create(
        [
            RankHistoryResponse(
                overall=h.overall,
                country=h.country,
                captured_at=h.captured_at,
            )
            for h in result
        ],
    )


@router.get(
    "/{user_id}/history/pp",
    response_model=response.BaseResponse[list[PPHistoryResponse]],
)
async def get_user_pp_history(
    ctx: RequiresContext,
    user_id: int,
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
) -> Response:
    result = await user_history.get_pp_history(ctx, user_id, mode, playstyle)
    result = response.unwrap(result)

    return response.create(
        [
            PPHistoryResponse(
                pp=h.pp,
                captured_at=h.captured_at,
            )
            for h in result
        ],
    )


class MostPlayedBeatmapResponse(BaseModel):
    beatmap_id: int
    beatmapset_id: int
    song_name: str


class MostPlayedResponse(BaseModel):
    beatmap: MostPlayedBeatmapResponse
    playcount: int


@router.get(
    "/{user_id}/beatmaps/most-played",
    response_model=response.BaseResponse[list[MostPlayedResponse]],
)
async def get_user_most_played(
    ctx: RequiresContext,
    user_id: int,
    mode: int = Query(0, ge=0, le=3),
    playstyle: int = Query(0, ge=0, le=2),
    page: int = Query(1, ge=1),
    limit: int = Query(5, ge=1, le=50),
) -> Response:
    result = await beatmaps.get_user_most_played(
        ctx,
        user_id,
        mode,
        playstyle,
        page,
        limit,
    )
    result = response.unwrap(result)

    return response.create(
        [
            MostPlayedResponse(
                beatmap=MostPlayedBeatmapResponse(
                    beatmap_id=mp.beatmap.beatmap_id,
                    beatmapset_id=mp.beatmap.beatmapset_id,
                    song_name=mp.beatmap.song_name,
                ),
                playcount=mp.playcount,
            )
            for mp in result
        ],
    )
