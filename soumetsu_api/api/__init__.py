from __future__ import annotations

import uuid
from collections.abc import Awaitable
from collections.abc import Callable

from fastapi import APIRouter
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from starlette.responses import Response

from soumetsu_api import settings
from soumetsu_api.adapters import mysql
from soumetsu_api.adapters import redis
from soumetsu_api.adapters import storage
from soumetsu_api.utilities import logging

from . import v2
from .v2.response import ServiceInterruptionException

logger = logging.get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI()

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

        try:
            return await call_next(request)
        finally:
            logging.clear_context()


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
