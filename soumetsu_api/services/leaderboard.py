from __future__ import annotations

from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.resources.leaderboard import FirstPlaceEntry
from soumetsu_api.resources.leaderboard import LeaderboardEntry
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError


class LeaderboardError(ServiceError):
    INVALID_MODE = "invalid_mode"
    INVALID_PLAYSTYLE = "invalid_playstyle"

    @override
    def service(self) -> str:
        return "leaderboard"

    @override
    def status_code(self) -> int:
        match self:
            case LeaderboardError.INVALID_MODE | LeaderboardError.INVALID_PLAYSTYLE:
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class LeaderboardModeStatsResult:
    pp: int
    accuracy: float
    playcount: int
    level: float


@dataclass
class LeaderboardEntryResult:
    id: int
    username: str
    country: str
    privileges: int
    chosen_mode: LeaderboardModeStatsResult
    rank: int


@dataclass
class FirstPlaceResult:
    player_id: int
    username: str
    score_id: int
    beatmap_md5: str
    song_name: str
    pp: float
    achieved_at: int
    mode: int


def _entry_to_result(e: LeaderboardEntry) -> LeaderboardEntryResult:
    return LeaderboardEntryResult(
        id=e.id,
        username=e.username,
        country=e.country,
        privileges=e.privileges,
        chosen_mode=LeaderboardModeStatsResult(
            pp=e.chosen_mode.pp,
            accuracy=e.chosen_mode.accuracy,
            playcount=e.chosen_mode.playcount,
            level=e.chosen_mode.level,
        ),
        rank=e.rank,
    )


def _first_to_result(f: FirstPlaceEntry) -> FirstPlaceResult:
    return FirstPlaceResult(
        player_id=f.player_id,
        username=f.username,
        score_id=f.score_id,
        beatmap_md5=f.beatmap_md5,
        song_name=f.song_name,
        pp=f.pp,
        achieved_at=f.achieved_at,
        mode=f.mode,
    )


async def get_global(
    ctx: AbstractContext,
    mode: int = 0,
    playstyle: int = 0,
    page: int = 1,
    limit: int = 50,
) -> LeaderboardError.OnSuccess[list[LeaderboardEntryResult]]:
    if mode < 0 or mode > 3:
        return LeaderboardError.INVALID_MODE

    if playstyle < 0 or playstyle > 2:
        return LeaderboardError.INVALID_PLAYSTYLE

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    entries = await ctx.leaderboard.get_global(mode, playstyle, limit, offset)
    return [_entry_to_result(e) for e in entries]


async def get_country(
    ctx: AbstractContext,
    country: str,
    mode: int = 0,
    playstyle: int = 0,
    page: int = 1,
    limit: int = 50,
) -> LeaderboardError.OnSuccess[list[LeaderboardEntryResult]]:
    if mode < 0 or mode > 3:
        return LeaderboardError.INVALID_MODE

    if playstyle < 0 or playstyle > 2:
        return LeaderboardError.INVALID_PLAYSTYLE

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    entries = await ctx.leaderboard.get_country(country, mode, playstyle, limit, offset)
    return [_entry_to_result(e) for e in entries]


async def get_rank_for_pp(
    ctx: AbstractContext,
    pp: int,
    mode: int = 0,
    playstyle: int = 0,
) -> LeaderboardError.OnSuccess[int]:
    if mode < 0 or mode > 3:
        return LeaderboardError.INVALID_MODE

    if playstyle < 0 or playstyle > 2:
        return LeaderboardError.INVALID_PLAYSTYLE

    return await ctx.leaderboard.get_rank_for_pp(pp, mode, playstyle)


async def list_oldest_firsts(
    ctx: AbstractContext,
    mode: int = 0,
    playstyle: int = 0,
    page: int = 1,
    limit: int = 50,
) -> LeaderboardError.OnSuccess[list[FirstPlaceResult]]:
    if mode < 0 or mode > 3:
        return LeaderboardError.INVALID_MODE

    if playstyle < 0 or playstyle > 2:
        return LeaderboardError.INVALID_PLAYSTYLE

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    entries = await ctx.leaderboard.list_oldest_firsts(mode, playstyle, limit, offset)
    return [_first_to_result(f) for f in entries]
