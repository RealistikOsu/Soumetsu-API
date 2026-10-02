from __future__ import annotations

import mimetypes
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


def _image(path: Path, max_age: int) -> FileResponse:
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": f"public, max-age={max_age}"},
    )


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
        directory = Path(settings.AVATAR_PATH)

        # Their own avatar first (gifs are kept for supporters), otherwise whatever default.* the
        # directory holds, so nobody gets a broken image.
        for suffix in ("png", "gif"):
            own = directory / f"{user_id}.{suffix}"
            if own.is_file():
                return _image(own, 7200)

        fallback = next((f for f in sorted(directory.glob("default.*")) if f.is_file()), None)
        if fallback is None:
            raise HTTPException(status_code=404)
        return _image(fallback, 600)

    @router.get("/assets/banners/{user_id}.png")
    async def get_banner(user_id: int):
        path = Path(settings.BANNER_PATH) / f"{user_id}.png"
        if not path.is_file():
            raise HTTPException(status_code=404)
        return _image(path, 7200)

    return router
