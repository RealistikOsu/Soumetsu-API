from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import override

from fastapi import status

from soumetsu_api.resources.ranked_play import MatchData
from soumetsu_api.resources.ranked_play import MatchPlayerData
from soumetsu_api.resources.ranked_play import MatchRoundData
from soumetsu_api.resources.ranked_play import MatchScoreData
from soumetsu_api.resources.ranked_play import MatchUserData
from soumetsu_api.resources.ranked_play import RoundBeatmapData
from soumetsu_api.resources.sessions import SessionData
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.services.beatmaps import split_song
from soumetsu_api.utilities import privileges


class RankedPlayError(ServiceError):
    MATCH_NOT_FOUND = "match_not_found"
    USER_NOT_FOUND = "user_not_found"
    USER_RESTRICTED = "user_restricted"

    @override
    def service(self) -> str:
        return "ranked_play"

    @override
    def status_code(self) -> int:
        match self:
            case RankedPlayError.MATCH_NOT_FOUND | RankedPlayError.USER_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case RankedPlayError.USER_RESTRICTED:
                return status.HTTP_403_FORBIDDEN
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class UserRef:
    id: int
    username: str
    country: str


@dataclass
class BeatmapRef:
    id: int
    set_id: int
    artist: str
    title: str
    version: str
    creator: str
    ranked_status: int
    star_rating: float | None
    mode: int


@dataclass
class MatchSummary:
    id: int
    name: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    winner_id: int | None
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
    round: int
    ruleset: int
    beatmap: BeatmapRef


@dataclass
class MatchDetailResult:
    match: MatchSummary
    participants: list[Participant]
    maps: list[MapEntry]


@dataclass
class RoundScore:
    user: UserRef
    total_score: int
    accuracy: float
    max_combo: int
    rank: str
    passed: bool
    statistics: dict[str, int]


@dataclass
class RoundDetail:
    number: int
    started_at: datetime
    ended_at: datetime | None
    ruleset: int
    beatmap: BeatmapRef
    scores: list[RoundScore]


@dataclass
class MatchEvent:
    type: str
    at: datetime
    user: UserRef | None = None
    round: int | RoundDetail | None = None


@dataclass
class MatchEventsResult:
    match: MatchSummary
    events: list[MatchEvent]


_STATISTIC_KEYS = ("great", "ok", "meh", "miss")

# A round card opens where its round starts and its end marker closes it, so on a tie the card comes first.
_EVENT_ORDER = {"round": 0, "joined": 1, "left": 1, "disbanded": 2, "round_ended": 2}


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC)


def parse_statistics(raw: str) -> dict[str, int]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}
    return {key: int(parsed.get(key, 0)) for key in _STATISTIC_KEYS}


def is_visible(user: MatchUserData) -> bool:
    return not privileges.is_restricted(privileges.UserPrivileges(user.privileges))


def user_ref(user: MatchUserData) -> UserRef:
    return UserRef(id=user.id, username=user.username, country=user.country)


def beatmap_ref(row: RoundBeatmapData) -> BeatmapRef:
    artist, title, version = split_song(row.song_name or "")
    stars = row.stars if row.stars and row.stars > 0 else None
    return BeatmapRef(
        id=row.beatmap_id,
        set_id=row.beatmapset_id or 0,
        artist=artist,
        title=title,
        version=version,
        creator=row.creator or "",
        ranked_status=row.ranked if row.ranked is not None else 0,
        star_rating=stars,
        mode=row.ruleset_id,
    )


def build_summary(
    match: MatchData,
    players: list[UserRef],
    rounds: list[MatchRoundData],
) -> MatchSummary:
    stars = [r.stars for r in rounds if r.stars and r.stars > 0]
    set_ids = [rounds[0].beatmapset_id, rounds[-1].beatmapset_id] if rounds else []
    name = match.name
    if not name:
        names = " vs ".join(p.username for p in players)
        name = f"Ranked Play: {names}" if names else "Ranked Play"

    return MatchSummary(
        id=match.id,
        name=name,
        status=match.status,
        started_at=as_utc(match.started_at),
        ended_at=as_utc(match.ended_at) if match.ended_at else None,
        winner_id=match.winner_user_id,
        map_count=len(rounds),
        players=players,
        star_min=min(stars, default=None),
        star_max=max(stars, default=None),
        cover_set_ids=list(dict.fromkeys(s for s in set_ids if s)),
    )


def rank_participants(
    players: list[UserRef],
    scores: list[MatchScoreData],
) -> list[Participant]:
    totals = {p.id: (0, 0.0, 0) for p in players}
    for score in scores:
        if score.user_id in totals:
            total, accuracy, count = totals[score.user_id]
            totals[score.user_id] = (
                total + score.total_score,
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


def round_detail(
    row: MatchRoundData,
    scores: list[MatchScoreData],
    users: dict[int, UserRef],
) -> RoundDetail:
    return RoundDetail(
        number=row.round,
        started_at=as_utc(row.started_at),
        ended_at=as_utc(row.ended_at) if row.ended_at else None,
        ruleset=row.ruleset_id,
        beatmap=beatmap_ref(row),
        scores=[
            RoundScore(
                user=users[s.user_id],
                total_score=s.total_score,
                accuracy=s.accuracy,
                max_combo=s.max_combo,
                rank=s.rank,
                passed=s.passed,
                statistics=parse_statistics(s.statistics),
            )
            for s in sorted(scores, key=lambda s: -s.total_score)
            if s.round == row.round and s.user_id in users
        ],
    )


async def _summaries(
    ctx: AbstractContext,
    matches: list[MatchData],
) -> tuple[list[MatchSummary], list[MatchRoundData]]:
    ids = [m.id for m in matches]
    players = await ctx.ranked_play.list_players(ids)
    rounds = await ctx.ranked_play.list_rounds(ids)

    summaries = [
        build_summary(
            match,
            [user_ref(p) for p in players if p.match_id == match.id and is_visible(p)],
            [r for r in rounds if r.match_id == match.id],
        )
        for match in matches
    ]
    return summaries, rounds


async def get_user_matches(
    ctx: AbstractContext,
    user_id: int,
    page: int,
    limit: int,
    viewer: SessionData | None = None,
) -> RankedPlayError.OnSuccess[UserMatchesResult]:
    user = await ctx.users.find_by_id(user_id)
    if not user:
        return RankedPlayError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if not privileges.can_view(user.id, user_privs, viewer):
        return RankedPlayError.USER_RESTRICTED

    active = (
        await ctx.ranked_play.list_user_matches(user_id, "active") if page == 1 else []
    )
    ended = await ctx.ranked_play.list_user_matches(
        user_id,
        "ended",
        limit,
        (page - 1) * limit,
    )
    total_ended = await ctx.ranked_play.count_user_matches(user_id, "ended")

    summaries, _ = await _summaries(ctx, active + ended)
    return UserMatchesResult(
        active=summaries[: len(active)],
        ended=summaries[len(active) :],
        total_ended=total_ended,
    )


async def get_match(
    ctx: AbstractContext,
    match_id: int,
) -> RankedPlayError.OnSuccess[MatchDetailResult]:
    match = await ctx.ranked_play.find_match(match_id)
    if not match:
        return RankedPlayError.MATCH_NOT_FOUND

    summaries, rounds = await _summaries(ctx, [match])
    summary = summaries[0]
    scores = await ctx.ranked_play.list_scores(match_id)

    return MatchDetailResult(
        match=summary,
        participants=rank_participants(summary.players, scores),
        maps=[
            MapEntry(round=r.round, ruleset=r.ruleset_id, beatmap=beatmap_ref(r))
            for r in rounds
        ],
    )


async def get_match_events(
    ctx: AbstractContext,
    match_id: int,
) -> RankedPlayError.OnSuccess[MatchEventsResult]:
    match = await ctx.ranked_play.find_match(match_id)
    if not match:
        return RankedPlayError.MATCH_NOT_FOUND

    summaries, rounds = await _summaries(ctx, [match])
    scores = await ctx.ranked_play.list_scores(match_id)
    raw_events = await ctx.ranked_play.list_events(match_id)

    user_ids = {s.user_id for s in scores} | {
        e.user_id for e in raw_events if e.user_id is not None
    }
    users = {
        u.id: user_ref(u)
        for u in await ctx.ranked_play.list_users(sorted(user_ids))
        if is_visible(u)
    }

    events = [
        MatchEvent(
            type=e.type,
            at=as_utc(e.created_at),
            user=users.get(e.user_id) if e.user_id is not None else None,
        )
        for e in raw_events
        if e.user_id is None or e.user_id in users
    ]
    for r in rounds:
        detail = round_detail(r, scores, users)
        events.append(MatchEvent(type="round", at=detail.started_at, round=detail))
        if detail.ended_at:
            events.append(
                MatchEvent(type="round_ended", at=detail.ended_at, round=r.round),
            )

    events.sort(key=lambda e: (e.at, _EVENT_ORDER.get(e.type, 1)))
    return MatchEventsResult(match=summaries[0], events=events)
