from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi_limiter import FastAPILimiter
from starlette.responses import Response

from soumetsu_api import settings
from soumetsu_api.adapters import mysql
from soumetsu_api.adapters import redis
from soumetsu_api.adapters import storage
from soumetsu_api.utilities import logging
from soumetsu_api.utilities import statsd

from . import v2
from .v2.response import ServiceInterruptionException

logger = logging.get_logger(__name__)


DESCRIPTION = """\
The API behind the RealistikOsu website. Every response is wrapped as `{ "status": 200, "data": ... }`,
and errors carry their code in `data`.

Most endpoints are public. Endpoints about your own account need the token you get from logging in,
sent as `Authorization: Bearer <token>`.
"""

TAG_ORDER = (
    "Users",
    "Scores",
    "Beatmaps",
    "Leaderboards",
    "Clans",
    "Friends",
    "Comments",
    "Badges",
    "Multiplayer",
    "Daily challenge",
    "Playlists",
    "Ranked play",
    "Auth",
    "Assets",
    "osu! API compatible",
    "Misc",
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="RealistikOsu API v2",
        version="2.0",
        description=DESCRIPTION,
        openapi_tags=[{"name": name} for name in TAG_ORDER],
        servers=[{"url": "https://ussr.pl"}],
        docs_url="/api/v2/docs",
        redoc_url="/api/v2/redoc",
        openapi_url="/api/v2/openapi.json",
    )
    initialise_openapi(app)

    initialise_cors(app)
    initialise_mysql(app)
    initialise_redis(app)
    initialise_storage(app)
    initialise_request_tracing(app)
    initialise_interruptions(app)
    initialise_rate_limiting(app)

    create_routes(app)

    logger.debug("Finalised app instance.")
    return app


def initialise_openapi(app: FastAPI) -> None:
    # Tokens are read from the header by hand rather than through a security dependency, so the
    # scheme has to be added to the generated spec here.
    def openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=app.servers,
        )
        schema.setdefault("components", {})["securitySchemes"] = {
            "token": {"type": "http", "scheme": "bearer"},
        }
        schema["security"] = [{}, {"token": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = openapi


def initialise_cors(app: FastAPI) -> None:
    if not settings.CORS_ALLOWED_ORIGINS:
        logger.debug("CORS not configured - no allowed origins specified.")
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.debug(
        "Configured CORS middleware.",
        extra={"allowed_origins": settings.CORS_ALLOWED_ORIGINS},
    )


def create_routes(app: FastAPI) -> None:
    router = APIRouter(
        prefix="/api",
    )

    router.include_router(v2.create_router())

    app.include_router(router)
    logger.debug("Attached routers to the app instance.")


def initialise_mysql(app: FastAPI) -> None:
    database = mysql.default()

    app.state.mysql = database

    # Lifecycle management
    @app.on_event("startup")
    async def on_startup() -> None:
        await app.state.mysql.connect()
        logger.info(
            "Connected to the MySQL database.",
        )

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await app.state.mysql.disconnect()

    logger.debug(
        "Attached MySQL to the app instance.",
    )


def initialise_redis(app: FastAPI) -> None:
    app.state.redis = redis.default()

    # Lifecycle management
    @app.on_event("startup")
    async def on_startup() -> None:
        await app.state.redis.initialise()
        logger.info(
            "Connected to the Redis database.",
        )

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await app.state.redis.aclose()
        logger.info(
            "Disconnected from the Redis database.",
        )

    logger.debug(
        "Attached Redis to the app instance.",
    )


def initialise_storage(app: FastAPI) -> None:
    storage_adapter = storage.default()
    storage_adapter.ensure_directories()

    app.state.storage = storage_adapter

    logger.debug("Attached storage to the app instance.")


def initialise_request_tracing(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_tracing(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.uuid = str(uuid.uuid4())

        logging.add_context(
            uuid=request.state.uuid,
        )

        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            logging.clear_context()

        route = request.scope.get("route")
        statsd.timing(
            "soumetsu_api.request.time",
            (time.perf_counter() - started) * 1000,
            [
                f"route:{route.path if route else 'unmatched'}",
                f"status:{response.status_code // 100}xx",
            ],
        )
        return response


def initialise_interruptions(app: FastAPI) -> None:
    @app.exception_handler(ServiceInterruptionException)
    async def service_interruption_exception_handler(
        _: Request,
        exc: ServiceInterruptionException,
    ):
        return exc.response

    logger.debug("Initialised service interruption handler for app instance.")


def initialise_rate_limiting(app: FastAPI) -> None:
    @app.on_event("startup")
    async def on_startup() -> None:
        await FastAPILimiter.init(
            app.state.redis,
            prefix="soumetsuapi:rate_limit",
        )

    logger.debug("Initialised rate limiting for app instance.")
