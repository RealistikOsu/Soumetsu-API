from __future__ import annotations

from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.constants import is_valid_custom_mode
from soumetsu_api.constants import is_valid_mode
from soumetsu_api.resources.clans import CLAN_PERM_MEMBER
from soumetsu_api.resources.clans import CLAN_PERM_OWNER
from soumetsu_api.resources.clans import ClanData
from soumetsu_api.resources.clans import ClanMemberData
from soumetsu_api.resources.clans import ClanMemberLeaderboardEntry
from soumetsu_api.resources.clans import ClanMemberStats
from soumetsu_api.resources.clans import ClanTopScore
from soumetsu_api.resources.leaderboard import _calculate_level
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import crypto


class ClanError(ServiceError):
    CLAN_NOT_FOUND = "clan_not_found"
    NOT_OWNER = "not_owner"
    NOT_MEMBER = "not_member"
    ALREADY_IN_CLAN = "already_in_clan"
    CLAN_FULL = "clan_full"
    INVALID_INVITE = "invalid_invite"
    NAME_TAKEN = "name_taken"
    TAG_TAKEN = "tag_taken"
    CANNOT_KICK_OWNER = "cannot_kick_owner"
    USER_NOT_IN_CLAN = "user_not_in_clan"
    INVALID_MODE = "invalid_mode"
    INVALID_CUSTOM_MODE = "invalid_custom_mode"

    @override
    def service(self) -> str:
        return "clans"

    @override
    def status_code(self) -> int:
        match self:
            case ClanError.CLAN_NOT_FOUND | ClanError.USER_NOT_IN_CLAN:
                return status.HTTP_404_NOT_FOUND
            case (
                ClanError.NOT_OWNER | ClanError.NOT_MEMBER | ClanError.CANNOT_KICK_OWNER
            ):
                return status.HTTP_403_FORBIDDEN
            case (
                ClanError.ALREADY_IN_CLAN
                | ClanError.CLAN_FULL
                | ClanError.NAME_TAKEN
                | ClanError.TAG_TAKEN
            ):
                return status.HTTP_409_CONFLICT
            case ClanError.INVALID_INVITE | ClanError.INVALID_MODE | ClanError.INVALID_CUSTOM_MODE:
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class ClanResult:
    id: int
    name: str
    description: str
    icon: str
    tag: str
    member_limit: int
    member_count: int


@dataclass
class ClanMemberResult:
    user_id: int
    username: str
    country: str
    is_owner: bool


def _clan_to_result(c: ClanData, member_count: int) -> ClanResult:
    return ClanResult(
        id=c.id,
        name=c.name,
        description=c.description,
        icon=c.icon,
        tag=c.tag,
        member_limit=c.member_limit,
        member_count=member_count,
    )


@dataclass
class ClanStatsResult:
    total_pp: int
    average_pp: int
    total_ranked_score: int
    total_total_score: int
    total_playcount: int
    total_replays_watched: int
    total_hits: int
    rank: int


@dataclass
class ClanModeStatsResult:
    pp: int
    ranked_score: int
    total_score: int
    playcount: int


@dataclass
class ClanLeaderboardEntryResult:
    id: int
    name: str
    tag: str
    icon: str
    chosen_mode: ClanModeStatsResult
    rank: int
    member_count: int


@dataclass
class ClanTopScoreResult:
    id: int
    player_id: int
    username: str
    pp: float
    accuracy: float
    mods: int
    max_combo: int
    beatmap_id: int
    beatmapset_id: int
    song_name: str
    difficulty: float
    ranked: int


@dataclass
class ClanMemberLeaderboardResult:
    id: int
    username: str
    country: str
    pp: int
    accuracy: float
    playcount: int
    level: float


def _compute_weighted_pp(member_stats: list[ClanMemberStats]) -> int:
    total = 0.0
    for i, m in enumerate(member_stats):
        total += m.pp * (0.95**i)
    return int(total)


def _member_to_result(m: ClanMemberData) -> ClanMemberResult:
    return ClanMemberResult(
        user_id=m.user_id,
        username=m.username,
        country=m.country,
        is_owner=m.perms == CLAN_PERM_OWNER,
    )


async def get_clan(
    ctx: AbstractContext,
    clan_id: int,
) -> ClanError.OnSuccess[ClanResult]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    member_count = await ctx.clans.get_member_count(clan_id)
    return _clan_to_result(clan, member_count)


async def search_clans(
    ctx: AbstractContext,
    query: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> ClanError.OnSuccess[list[ClanResult]]:
    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    clans = await ctx.clans.search(query, limit, offset)
    results = []
    for c in clans:
        member_count = await ctx.clans.get_member_count(c.id)
        results.append(_clan_to_result(c, member_count))

    return results


async def create_clan(
    ctx: AbstractContext,
    user_id: int,
    name: str,
    tag: str,
    description: str = "",
) -> ClanError.OnSuccess[ClanResult]:
    if await ctx.clans.get_user_clan(user_id):
        return ClanError.ALREADY_IN_CLAN

    if await ctx.clans.name_exists(name):
        return ClanError.NAME_TAKEN

    if await ctx.clans.tag_exists(tag):
        return ClanError.TAG_TAKEN

    clan_id = await ctx.clans.create(name, description, tag)
    await ctx.clans.add_member(clan_id, user_id, CLAN_PERM_OWNER)

    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    return _clan_to_result(clan, 1)


async def update_clan(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
    name: str | None = None,
    description: str | None = None,
    icon: str | None = None,
) -> ClanError.OnSuccess[ClanResult]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    if name and name != clan.name:
        if await ctx.clans.name_exists(name):
            return ClanError.NAME_TAKEN

    await ctx.clans.update(clan_id, name, description, icon)

    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    member_count = await ctx.clans.get_member_count(clan_id)
    return _clan_to_result(clan, member_count)


async def delete_clan(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
) -> ClanError.OnSuccess[None]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    await ctx.clans.delete(clan_id)
    return None


async def get_members(
    ctx: AbstractContext,
    clan_id: int,
    page: int = 1,
    limit: int = 50,
) -> ClanError.OnSuccess[list[ClanMemberResult]]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    members = await ctx.clans.get_members(clan_id, limit, offset)
    return [_member_to_result(m) for m in members]


async def join_clan(
    ctx: AbstractContext,
    user_id: int,
    invite: str,
) -> ClanError.OnSuccess[ClanResult]:
    if await ctx.clans.get_user_clan(user_id):
        return ClanError.ALREADY_IN_CLAN

    clan_id = await ctx.clans.get_clan_by_invite(invite)
    if not clan_id:
        return ClanError.INVALID_INVITE

    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    added = await ctx.clans.add_member_with_atomic_limit(
        clan_id,
        user_id,
        clan.member_limit,
        CLAN_PERM_MEMBER,
    )
    if not added:
        return ClanError.CLAN_FULL

    member_count = await ctx.clans.get_member_count(clan_id)
    return _clan_to_result(clan, member_count)


async def leave_clan(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
) -> ClanError.OnSuccess[None]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms is None:
        return ClanError.NOT_MEMBER

    if perms == CLAN_PERM_OWNER:
        await ctx.clans.delete(clan_id)
    else:
        await ctx.clans.remove_member(clan_id, user_id)

    return None


async def kick_member(
    ctx: AbstractContext,
    owner_id: int,
    clan_id: int,
    user_id: int,
) -> ClanError.OnSuccess[None]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    owner_perms = await ctx.clans.get_user_perms(owner_id, clan_id)
    if owner_perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    user_perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if user_perms is None:
        return ClanError.USER_NOT_IN_CLAN

    if user_perms == CLAN_PERM_OWNER:
        return ClanError.CANNOT_KICK_OWNER

    await ctx.clans.remove_member(clan_id, user_id)
    return None


async def get_invite(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
) -> ClanError.OnSuccess[str]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    invite = await ctx.clans.get_invite(clan_id)
    if not invite:
        invite = crypto.generate_token(8)
        await ctx.clans.set_invite(clan_id, invite)

    return invite


async def regenerate_invite(
    ctx: AbstractContext,
    user_id: int,
    clan_id: int,
) -> ClanError.OnSuccess[str]:
    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    perms = await ctx.clans.get_user_perms(user_id, clan_id)
    if perms != CLAN_PERM_OWNER:
        return ClanError.NOT_OWNER

    invite = crypto.generate_token(8)
    await ctx.clans.set_invite(clan_id, invite)

    return invite


async def get_clan_stats(
    ctx: AbstractContext,
    clan_id: int,
    mode: int = 0,
    custom_mode: int = 0,
) -> ClanError.OnSuccess[ClanStatsResult]:
    if not is_valid_mode(mode):
        return ClanError.INVALID_MODE

    if not is_valid_custom_mode(custom_mode):
        return ClanError.INVALID_CUSTOM_MODE

    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    member_stats = await ctx.clans.get_clan_member_stats(clan_id, mode, custom_mode)

    if not member_stats:
        return ClanStatsResult(
            total_pp=0,
            average_pp=0,
            total_ranked_score=0,
            total_total_score=0,
            total_playcount=0,
            total_replays_watched=0,
            total_hits=0,
            rank=0,
        )

    total_pp = _compute_weighted_pp(member_stats)
    average_pp = sum(m.pp for m in member_stats) // len(member_stats)
    total_ranked_score = sum(m.ranked_score for m in member_stats)
    total_total_score = sum(m.total_score for m in member_stats)
    total_playcount = sum(m.playcount for m in member_stats)
    total_replays_watched = sum(m.replays_watched for m in member_stats)
    total_hits = sum(m.total_hits for m in member_stats)

    # Compute rank by comparing against all clans
    all_clan_ids = await ctx.clans.get_all_clan_ids()
    rank = 1
    for other_clan_id in all_clan_ids:
        if other_clan_id == clan_id:
            continue
        other_stats = await ctx.clans.get_clan_member_stats(
            other_clan_id,
            mode,
            custom_mode,
        )
        other_pp = _compute_weighted_pp(other_stats)
        if other_pp > total_pp:
            rank += 1

    return ClanStatsResult(
        total_pp=total_pp,
        average_pp=average_pp,
        total_ranked_score=total_ranked_score,
        total_total_score=total_total_score,
        total_playcount=total_playcount,
        total_replays_watched=total_replays_watched,
        total_hits=total_hits,
        rank=rank,
    )


async def get_clan_leaderboard(
    ctx: AbstractContext,
    mode: int = 0,
    custom_mode: int = 0,
    page: int = 1,
    limit: int = 50,
) -> ClanError.OnSuccess[list[ClanLeaderboardEntryResult]]:
    if not is_valid_mode(mode):
        return ClanError.INVALID_MODE

    if not is_valid_custom_mode(custom_mode):
        return ClanError.INVALID_CUSTOM_MODE

    if limit > 100:
        limit = 100

    all_clan_ids = await ctx.clans.get_all_clan_ids()

    clan_entries: list[tuple[int, ClanData, ClanMemberStats, int, int]] = []
    for clan_id in all_clan_ids:
        clan = await ctx.clans.get_by_id(clan_id)
        if not clan:
            continue

        member_stats = await ctx.clans.get_clan_member_stats(
            clan_id,
            mode,
            custom_mode,
        )
        if not member_stats:
            continue

        weighted_pp = _compute_weighted_pp(member_stats)
        total_ranked_score = sum(m.ranked_score for m in member_stats)
        total_score = sum(m.total_score for m in member_stats)
        total_playcount = sum(m.playcount for m in member_stats)
        member_count = await ctx.clans.get_member_count(clan_id)

        total_replays_watched = sum(m.replays_watched for m in member_stats)
        total_hits = sum(m.total_hits for m in member_stats)

        clan_entries.append((
            weighted_pp,
            clan,
            ClanMemberStats(
                pp=weighted_pp,
                ranked_score=total_ranked_score,
                total_score=total_score,
                playcount=total_playcount,
                replays_watched=total_replays_watched,
                total_hits=total_hits,
            ),
            member_count,
            clan_id,
        ))

    clan_entries.sort(key=lambda x: x[0], reverse=True)

    offset = (page - 1) * limit
    paginated = clan_entries[offset : offset + limit]

    results = []
    for i, (_, clan, stats, member_count, _) in enumerate(paginated):
        results.append(
            ClanLeaderboardEntryResult(
                id=clan.id,
                name=clan.name,
                tag=clan.tag,
                icon=clan.icon,
                chosen_mode=ClanModeStatsResult(
                    pp=stats.pp,
                    ranked_score=stats.ranked_score,
                    total_score=stats.total_score,
                    playcount=stats.playcount,
                ),
                rank=offset + i + 1,
                member_count=member_count,
            ),
        )

    return results


async def get_clan_top_scores(
    ctx: AbstractContext,
    clan_id: int,
    mode: int = 0,
    custom_mode: int = 0,
    limit: int = 4,
) -> ClanError.OnSuccess[list[ClanTopScoreResult]]:
    if not is_valid_mode(mode):
        return ClanError.INVALID_MODE

    if not is_valid_custom_mode(custom_mode):
        return ClanError.INVALID_CUSTOM_MODE

    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    if limit > 100:
        limit = 100

    scores = await ctx.clans.get_clan_top_scores(clan_id, mode, custom_mode, limit)

    return [
        ClanTopScoreResult(
            id=s.id,
            player_id=s.player_id,
            username=s.username,
            pp=s.pp,
            accuracy=s.accuracy,
            mods=s.mods,
            max_combo=s.max_combo,
            beatmap_id=s.beatmap_id,
            beatmapset_id=s.beatmapset_id,
            song_name=s.song_name,
            difficulty=s.difficulty,
            ranked=s.ranked,
        )
        for s in scores
    ]


async def get_clan_member_leaderboard(
    ctx: AbstractContext,
    clan_id: int,
    mode: int = 0,
    custom_mode: int = 0,
) -> ClanError.OnSuccess[list[ClanMemberLeaderboardResult]]:
    if not is_valid_mode(mode):
        return ClanError.INVALID_MODE

    if not is_valid_custom_mode(custom_mode):
        return ClanError.INVALID_CUSTOM_MODE

    clan = await ctx.clans.get_by_id(clan_id)
    if not clan:
        return ClanError.CLAN_NOT_FOUND

    entries = await ctx.clans.get_clan_member_leaderboard(clan_id, mode, custom_mode)

    return [
        ClanMemberLeaderboardResult(
            id=e.id,
            username=e.username,
            country=e.country,
            pp=e.pp,
            accuracy=e.accuracy,
            playcount=e.playcount,
            level=_calculate_level(e.total_score),
        )
        for e in entries
    ]
