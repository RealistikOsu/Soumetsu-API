from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import override

from fastapi import status

from soumetsu_api.resources.multiplayer import GameData
from soumetsu_api.resources.multiplayer import GameScoreData
from soumetsu_api.resources.multiplayer import MatchData
from soumetsu_api.resources.sessions import SessionData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.services.ranked_play import BeatmapRef
from soumetsu_api.services.ranked_play import UserRef
from soumetsu_api.services.ranked_play import as_utc
from soumetsu_api.services.ranked_play import beatmap_ref
from soumetsu_api.services.ranked_play import is_visible
from soumetsu_api.services.ranked_play import user_ref
from soumetsu_api.utilities import privileges
from soumetsu_api.utilities.mods import OsuMods

SUMMARY_PLAYER_CAP = 16


class MultiplayerError(ServiceError):
    MATCH_NOT_FOUND = "match_not_found"
    USER_NOT_FOUND = "user_not_found"
    USER_RESTRICTED = "user_restricted"

    @override
    def service(self) -> str:
        return "multiplayer"

    @override
    def status_code(self) -> int:
        match self:
            case MultiplayerError.MATCH_NOT_FOUND | MultiplayerError.USER_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case MultiplayerError.USER_RESTRICTED:
                return status.HTTP_403_FORBIDDEN
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class MatchSummary:
    id: int
    name: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    host: UserRef | None
    map_count: int
    players: list[UserRef]
    star_min: float | None
    star_max: float | None
    cover_set_ids: list[int]


@dataclass
class UserMatchesResult:
    active: list[MatchSummary]
    ended: list[MatchSummary]
    total_ended: int


@dataclass
class Participant:
    user: UserRef
    rank: int
    accuracy: float
    play_count: int
    total_score: int


@dataclass
class MapEntry:
    game: int
    mode: int
    mods: int
    beatmap: BeatmapRef


@dataclass
class MatchDetailResult:
    match: MatchSummary
    participants: list[Participant]
    maps: list[MapEntry]


@dataclass
class GameScore:
    user: UserRef
    team: int
    score: int
    accuracy: float
    max_combo: int
    passed: bool
    mods: int
    grade: str
    statistics: dict[str, int]


@dataclass
class GameDetail:
    number: int
    started_at: datetime
    ended_at: datetime | None
    mode: int
    mods: int
    win_condition: int
    team_type: int
    beatmap: BeatmapRef
    scores: list[GameScore]


@dataclass
class MatchEvent:
    type: str
    at: datetime
    user: UserRef | None = None
    game: int | GameDetail | None = None


@dataclass
class MatchEventsResult:
    match: MatchSummary
    events: list[MatchEvent]


# A game card opens where the game starts and its end marker closes it, so on a tie the card comes first.
_EVENT_ORDER = {"game": 0, "joined": 1, "left": 1, "disbanded": 2, "game_ended": 2}

_SILVER_MODS = OsuMods.HD | OsuMods.FL

_ACCURACY_GRADES = {
    2: (98, 94, 90, 85),
    3: (95, 90, 80, 70),
}


def grade_of(mode: int, score: GameScoreData) -> str:
    if not score.passed:
        return "F"

    silver = bool(score.mods & _SILVER_MODS)
    top = "SSH" if silver else "SS"
    second = "SH" if silver else "S"

    if mode in _ACCURACY_GRADES:
        s, a, b, c = _ACCURACY_GRADES[mode]
        if score.accuracy >= 100:
            return top
        if score.accuracy > s:
            return second
        if score.accuracy > a:
            return "A"
        if score.accuracy > b:
            return "B"
        return "C" if score.accuracy > c else "D"

    total = score.count_300 + score.count_100 + score.count_miss
    if mode != 1:
        total += score.count_50
    if total == 0:
        return "D"

    r300 = score.count_300 / total
    r50 = score.count_50 / total if mode != 1 else 0
    misses = score.count_miss
    if r300 == 1:
        return top
    if r300 > 0.9 and r50 <= 0.01 and misses == 0:
        return second
    if (r300 > 0.8 and misses == 0) or r300 > 0.9:
        return "A"
    if (r300 > 0.7 and misses == 0) or r300 > 0.8:
        return "B"
    return "C" if r300 > 0.6 else "D"


def build_summary(
    match: MatchData,
    host: UserRef | None,
    players: list[UserRef],
    games: list[GameData],
) -> MatchSummary:
    stars = [g.stars for g in games if g.stars and g.stars > 0]
    set_ids = [games[0].beatmapset_id, games[-1].beatmapset_id] if games else []

    return MatchSummary(
        id=match.id,
        name=match.name,
        status=match.status,
        started_at=as_utc(match.created_at),
        ended_at=as_utc(match.ended_at) if match.ended_at else None,
        host=host,
        map_count=len(games),
        players=players[:SUMMARY_PLAYER_CAP],
        star_min=min(stars, default=None),
        star_max=max(stars, default=None),
        cover_set_ids=list(dict.fromkeys(s for s in set_ids if s)),
    )


def rank_participants(
    players: list[UserRef],
    scores: list[GameScoreData],
) -> list[Participant]:
    totals = {p.id: (0, 0.0, 0) for p in players}
    for score in scores:
        if score.user_id in totals:
            total, accuracy, count = totals[score.user_id]
            totals[score.user_id] = (
                total + score.score,
                accuracy + score.accuracy,
                count + 1,
            )

    participants = []
    for rank, player in enumerate(
        sorted(players, key=lambda p: (-totals[p.id][0], p.id)),
        start=1,
    ):
        total, accuracy, count = totals[player.id]
        participants.append(
            Participant(
                user=player,
                rank=rank,
                accuracy=round(accuracy / count, 2) if count else 0.0,
                play_count=count,
                total_score=total,
            ),
        )
    return participants


def game_detail(
    row: GameData,
    scores: list[GameScoreData],
    users: dict[int, UserRef],
) -> GameDetail:
    return GameDetail(
        number=row.game,
        started_at=as_utc(row.started_at),
        ended_at=as_utc(row.ended_at) if row.ended_at else None,
        mode=row.ruleset_id,
        mods=row.mods,
        win_condition=row.win_condition,
        team_type=row.team_type,
        beatmap=beatmap_ref(row),
        scores=[
            GameScore(
                user=users[s.user_id],
                team=s.team,
                score=s.score,
                accuracy=s.accuracy,
                max_combo=s.max_combo,
                passed=s.passed,
                mods=s.mods,
                grade=grade_of(row.ruleset_id, s),
                statistics={
                    "count_300": s.count_300,
                    "count_100": s.count_100,
                    "count_50": s.count_50,
                    "count_miss": s.count_miss,
                    "count_geki": s.count_geki,
                    "count_katu": s.count_katu,
                },
            )
            for s in sorted(scores, key=lambda s: -s.score)
            if s.game == row.game and s.user_id in users
        ],
    )


def merge_events(
    simple: list[MatchEvent],
    games: list[GameData],
    scores: list[GameScoreData],
    users: dict[int, UserRef],
) -> list[MatchEvent]:
    events = list(simple)
    for g in games:
        detail = game_detail(g, scores, users)
        events.append(MatchEvent(type="game", at=detail.started_at, game=detail))
        if detail.ended_at:
            events.append(
                MatchEvent(type="game_ended", at=detail.ended_at, game=g.game),
            )

    events.sort(key=lambda e: (e.at, _EVENT_ORDER.get(e.type, 1)))
    return events


async def _load(
    ctx: AbstractContext,
    matches: list[MatchData],
) -> tuple[list[MatchSummary], dict[int, list[UserRef]], list[GameData]]:
    ids = [m.id for m in matches]
    players = await ctx.multiplayer.list_players(ids)
    games = await ctx.multiplayer.list_games(ids)
    hosts = {
        u.id: user_ref(u)
        for u in await ctx.ranked_play.list_users(
            sorted({m.host_id for m in matches if m.host_id is not None}),
        )
        if is_visible(u)
    }

    roster: dict[int, list[UserRef]] = {m.id: [] for m in matches}
    for p in players:
        if is_visible(p):
            roster[p.match_id].append(user_ref(p))

    summaries = [
        build_summary(
            match,
            hosts.get(match.host_id) if match.host_id is not None else None,
            roster[match.id],
            [g for g in games if g.match_id == match.id],
        )
        for match in matches
    ]
    return summaries, roster, games


async def get_user_matches(
    ctx: AbstractContext,
    user_id: int,
    page: int,
    limit: int,
    viewer: SessionData | None = None,
) -> MultiplayerError.OnSuccess[UserMatchesResult]:
    user = await ctx.users.find_by_id(user_id)
    if not user:
        return MultiplayerError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if not privileges.can_view(user.id, user_privs, viewer):
        return MultiplayerError.USER_RESTRICTED

    active = (
        await ctx.multiplayer.list_user_matches(user_id, "active") if page == 1 else []
    )
    ended = await ctx.multiplayer.list_user_matches(
        user_id,
        "ended",
        limit,
        (page - 1) * limit,
    )
    total_ended = await ctx.multiplayer.count_user_matches(user_id, "ended")

    summaries, _, _ = await _load(ctx, active + ended)
    return UserMatchesResult(
        active=summaries[: len(active)],
        ended=summaries[len(active) :],
        total_ended=total_ended,
    )


async def get_match(
    ctx: AbstractContext,
    match_id: int,
) -> MultiplayerError.OnSuccess[MatchDetailResult]:
    match = await ctx.multiplayer.find_match(match_id)
    if not match:
        return MultiplayerError.MATCH_NOT_FOUND

    summaries, roster, games = await _load(ctx, [match])
    scores = await ctx.multiplayer.list_scores(match_id)

    return MatchDetailResult(
        match=summaries[0],
        participants=rank_participants(roster[match_id], scores),
        maps=[
            MapEntry(
                game=g.game, mode=g.ruleset_id, mods=g.mods, beatmap=beatmap_ref(g)
            )
            for g in games
        ],
    )


async def get_match_events(
    ctx: AbstractContext,
    match_id: int,
) -> MultiplayerError.OnSuccess[MatchEventsResult]:
    match = await ctx.multiplayer.find_match(match_id)
    if not match:
        return MultiplayerError.MATCH_NOT_FOUND

    summaries, _, games = await _load(ctx, [match])
    scores = await ctx.multiplayer.list_scores(match_id)
    raw_events = await ctx.multiplayer.list_events(match_id)

    user_ids = {s.user_id for s in scores} | {
        e.user_id for e in raw_events if e.user_id is not None
    }
    users = {
        u.id: user_ref(u)
        for u in await ctx.ranked_play.list_users(sorted(user_ids))
        if is_visible(u)
    }

    simple = [
        MatchEvent(
            type=e.type,
            at=as_utc(e.created_at),
            user=users.get(e.user_id) if e.user_id is not None else None,
        )
        for e in raw_events
        if e.user_id is None or e.user_id in users
    ]
    return MatchEventsResult(
        match=summaries[0],
        events=merge_events(simple, games, scores, users),
    )
