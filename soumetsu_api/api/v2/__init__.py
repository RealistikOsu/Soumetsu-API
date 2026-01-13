from __future__ import annotations

from fastapi import APIRouter

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
    router.include_router(users.router)

    return router
