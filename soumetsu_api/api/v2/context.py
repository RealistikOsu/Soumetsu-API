# =============================================================================
# WARNING: DO NOT ADD `from __future__ import annotations` TO THIS FILE
# =============================================================================
#
# FastAPI's dependency injection relies on runtime type introspection to resolve
# dependencies. When `from __future__ import annotations` is enabled (PEP 563),
# all annotations become forward references (strings) that are evaluated lazily.

# The workaround is to NOT use `from __future__ import annotations` in files
# that define FastAPI dependencies. All other files in this codebase use it.
# =============================================================================

from collections.abc import AsyncGenerator
from typing import Annotated
from typing import override

from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import status

from soumetsu_api.adapters.mysql import ImplementsMySQL
from soumetsu_api.adapters.mysql import MySQLPoolAdapter
from soumetsu_api.adapters.redis import RedisClient
from soumetsu_api.resources import SessionData
from soumetsu_api.resources import SessionRepository
from soumetsu_api.services import AbstractContext


class HTTPContext(AbstractContext):
    def __init__(self, request: Request) -> None:
        self.request = request

    @property
    @override
    def _mysql(self) -> ImplementsMySQL:
        return self.request.app.state.mysql

    @property
    @override
    def _redis(self) -> RedisClient:
        return self.request.app.state.redis


class HTTPTransactionContext(AbstractContext):
    def __init__(self, mysql: ImplementsMySQL, redis: RedisClient) -> None:
        self._mysql_conn = mysql
        self._redis_conn = redis

    @property
    @override
    def _mysql(self) -> ImplementsMySQL:
        return self._mysql_conn

    @property
    @override
    def _redis(self) -> RedisClient:
        return self._redis_conn


class AuthenticatedContext(HTTPContext):
    def __init__(self, request: Request, session: SessionData) -> None:
        super().__init__(request)
        self.session = session
        self.user_id = session.user_id
        self.privileges = session.privileges


class AuthenticatedTransactionContext(HTTPTransactionContext):
    def __init__(
        self,
        mysql: ImplementsMySQL,
        redis: RedisClient,
        session: SessionData,
    ) -> None:
        super().__init__(mysql, redis)
        self.session = session
        self.user_id = session.user_id
        self.privileges = session.privileges


async def _get_transaction_context(
    request: Request,
) -> AsyncGenerator[HTTPTransactionContext, None]:
    pool: MySQLPoolAdapter = request.app.state.mysql
    redis_client: RedisClient = request.app.state.redis

    async with pool.transaction() as transaction:
        yield HTTPTransactionContext(transaction, redis_client)


def _extract_token(authorization: str = Header(default="")) -> str | None:
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def _get_session(request: Request) -> SessionData | None:
    authorization = request.headers.get("Authorization", "")
    token = _extract_token(authorization)
    if not token:
        return None

    redis_client: RedisClient = request.app.state.redis
    sessions = SessionRepository(redis_client)
    return await sessions.get(token)


async def _require_auth(request: Request) -> AuthenticatedContext:
    session = await _get_session(request)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="auth.unauthenticated",
        )
    return AuthenticatedContext(request, session)


async def _require_auth_transaction(
    request: Request,
) -> AsyncGenerator[AuthenticatedTransactionContext, None]:
    session = await _get_session(request)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="auth.unauthenticated",
        )

    pool: MySQLPoolAdapter = request.app.state.mysql
    redis_client: RedisClient = request.app.state.redis

    async with pool.transaction() as transaction:
        yield AuthenticatedTransactionContext(transaction, redis_client, session)


RequiresContext = Annotated[HTTPContext, Depends(HTTPContext)]

RequiresTransaction = Annotated[
    HTTPTransactionContext,
    Depends(_get_transaction_context),
]

RequiresAuth = Annotated[AuthenticatedContext, Depends(_require_auth)]

RequiresAuthTransaction = Annotated[
    AuthenticatedTransactionContext,
    Depends(_require_auth_transaction),
]
