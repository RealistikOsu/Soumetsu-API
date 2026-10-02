from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.responses import FileResponse

from soumetsu_api import settings

from . import admin
from . import auth
from . import badges
from . import beatmaps
from . import clans
from . import comments
from . import friends
from . import health
from . import leaderboard
from . import peppy
from . import scores
from . import stats
from . import team
from . import users


def create_router() -> APIRouter:
    router = APIRouter(
        prefix="/v2",
    )

    router.include_router(admin.router)
    router.include_router(auth.router)
    router.include_router(badges.router)
    router.include_router(beatmaps.router)
    router.include_router(clans.router)
    router.include_router(comments.router)
    router.include_router(friends.router)
    router.include_router(health.router)
    router.include_router(leaderboard.router)
    router.include_router(peppy.router)
    router.include_router(scores.router)
    router.include_router(stats.router)
    router.include_router(team.router)
    router.include_router(users.router)

    @router.get("/assets/avatars/{user_id}.png")
    async def get_avatar(user_id: int):
        path = Path(settings.AVATAR_PATH) / f"{user_id}.png"
        if not path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(
            path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=7200"},
        )

    @router.get("/assets/banners/{user_id}.png")
    async def get_banner(user_id: int):
        path = Path(settings.BANNER_PATH) / f"{user_id}.png"
        if not path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(
            path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=7200"},
        )

    return router
