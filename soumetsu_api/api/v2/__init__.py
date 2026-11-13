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
from . import daily_stats
from . import friends
from . import health
from . import leaderboard
from . import multiplayer
from . import peppy
from . import ranked_play
from . import rooms
from . import scores
from . import stats
from . import team
from . import two_factor
from . import upload_requests
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

    router.include_router(admin.router, include_in_schema=False)
    router.include_router(auth.router, tags=["Auth"])
    router.include_router(badges.router, tags=["Badges"])
    router.include_router(beatmaps.router, tags=["Beatmaps"])
    router.include_router(clans.router, tags=["Clans"])
    router.include_router(comments.router, tags=["Comments"])
    router.include_router(daily_stats.router, tags=["Daily challenge"])
    router.include_router(friends.router, tags=["Friends"])
    router.include_router(health.router, tags=["Misc"])
    router.include_router(leaderboard.router, tags=["Leaderboards"])
    router.include_router(peppy.router, tags=["osu! API compatible"])
    router.include_router(ranked_play.router, tags=["Ranked play"])
    router.include_router(multiplayer.router, tags=["Multiplayer"])
    router.include_router(rooms.daily_router, tags=["Daily challenge"])
    router.include_router(rooms.playlist_router, tags=["Playlists"])
    router.include_router(scores.router, tags=["Scores"])
    router.include_router(stats.router, tags=["Misc"])
    router.include_router(team.router, tags=["Misc"])
    router.include_router(two_factor.router, tags=["Auth"])
    router.include_router(upload_requests.router, tags=["Beatmaps"])
    router.include_router(users.router, tags=["Users"])

    @router.get("/assets/avatars/{user_id}.png", tags=["Assets"])
    async def get_avatar(user_id: int):
        directory = Path(settings.AVATAR_PATH)

        # Their own avatar first, otherwise the default one, so nobody gets a broken image.
        # The order matches the avatar nginx vhost: a gif wins over a png.
        for suffix in ("gif", "png"):
            own = directory / f"{user_id}.{suffix}"
            if own.is_file():
                return _image(own, 7200)

        for name in ("default.gif", "default.png", "default"):
            if (directory / name).is_file():
                return _image(directory / name, 600)

        fallback = next(
            (f for f in sorted(directory.glob("default.*")) if f.is_file()), None
        )
        if fallback is None:
            raise HTTPException(status_code=404)
        return _image(fallback, 600)

    @router.get("/assets/banners/{user_id}.png", tags=["Assets"])
    async def get_banner(user_id: int):
        path = Path(settings.BANNER_PATH) / f"{user_id}.png"
        if not path.is_file():
            raise HTTPException(status_code=404)
        return _image(path, 7200)

    return router
