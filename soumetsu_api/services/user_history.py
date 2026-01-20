from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import override

from fastapi import status

from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import privileges


class UserHistoryError(ServiceError):
    USER_NOT_FOUND = "user_not_found"
    USER_RESTRICTED = "user_restricted"
    INVALID_TYPE = "invalid_type"

    @override
    def service(self) -> str:
        return "user_history"

    @override
    def status_code(self) -> int:
        match self:
            case UserHistoryError.USER_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case UserHistoryError.USER_RESTRICTED:
                return status.HTTP_403_FORBIDDEN
            case UserHistoryError.INVALID_TYPE:
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


class HistoryType(StrEnum):
    RANK = "rank"
    PP = "pp"


@dataclass
class RankHistoryResult:
    overall: int
    country: int | None
    captured_at: str


@dataclass
class PPHistoryResult:
    pp: int | None
    captured_at: str


async def get_rank_history(
    ctx: AbstractContext,
    user_id: int,
    mode: int,
    custom_mode: int,
) -> UserHistoryError.OnSuccess[list[RankHistoryResult]]:
    user = await ctx.users.find_by_id(user_id)
    if not user:
        return UserHistoryError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return UserHistoryError.USER_RESTRICTED

    # Mode combines mode and custom_mode: mode + custom_mode * 4
    combined_mode = mode + custom_mode * 4
    history = await ctx.user_history.get_history(user_id, combined_mode)

    return [
        RankHistoryResult(
            overall=h.rank,
            country=h.country_rank,
            captured_at=h.captured_at,
        )
        for h in reversed(history)  # Oldest first for graph
    ]


async def get_pp_history(
    ctx: AbstractContext,
    user_id: int,
    mode: int,
    custom_mode: int,
) -> UserHistoryError.OnSuccess[list[PPHistoryResult]]:
    user = await ctx.users.find_by_id(user_id)
    if not user:
        return UserHistoryError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return UserHistoryError.USER_RESTRICTED

    combined_mode = mode + custom_mode * 4
    history = await ctx.user_history.get_history(user_id, combined_mode)

    return [
        PPHistoryResult(
            pp=h.pp,
            captured_at=h.captured_at,
        )
        for h in reversed(history)  # Oldest first for graph
    ]
