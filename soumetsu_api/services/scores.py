from __future__ import annotations

from dataclasses import dataclass
from typing import override

from fastapi import status

from soumetsu_api.constants import is_valid_custom_mode
from soumetsu_api.constants import is_valid_mode
from soumetsu_api.resources.scores import ScoreData
from soumetsu_api.resources.scores import ScoreTopPlay
from soumetsu_api.resources.scores import ScoreWithBeatmap
from soumetsu_api.services._common import AbstractContext
from soumetsu_api.services._common import ServiceError
from soumetsu_api.utilities import privileges


class ScoreError(ServiceError):
    SCORE_NOT_FOUND = "score_not_found"
    USER_NOT_FOUND = "user_not_found"
    USER_RESTRICTED = "user_restricted"
    FORBIDDEN = "forbidden"
    ALREADY_PINNED = "already_pinned"
    NOT_PINNED = "not_pinned"
    NOT_YOUR_SCORE = "not_your_score"
    INVALID_MODE = "invalid_mode"
    INVALID_CUSTOM_MODE = "invalid_custom_mode"

    @override
    def service(self) -> str:
        return "scores"

    @override
    def status_code(self) -> int:
        match self:
            case ScoreError.SCORE_NOT_FOUND | ScoreError.USER_NOT_FOUND:
                return status.HTTP_404_NOT_FOUND
            case (
                ScoreError.USER_RESTRICTED
                | ScoreError.FORBIDDEN
                | ScoreError.NOT_YOUR_SCORE
            ):
                return status.HTTP_403_FORBIDDEN
            case ScoreError.ALREADY_PINNED | ScoreError.NOT_PINNED:
                return status.HTTP_409_CONFLICT
            case ScoreError.INVALID_MODE | ScoreError.INVALID_CUSTOM_MODE:
                return status.HTTP_400_BAD_REQUEST
            case _:
                return status.HTTP_500_INTERNAL_SERVER_ERROR


@dataclass
class ScoreResult:
    id: int
    beatmap_md5: str
    player_id: int
    score: int
    max_combo: int
    full_combo: bool
    mods: int
    count_300: int
    count_100: int
    count_50: int
    count_katus: int
    count_gekis: int
    count_misses: int
    submitted_at: int
    play_mode: int
    completed: int
    accuracy: float
    pp: float
    playtime: int


@dataclass
class ScoreWithBeatmapResult(ScoreResult):
    beatmap_id: int
    beatmapset_id: int
    song_name: str
    difficulty: float
    ranked: int


@dataclass
class ScoreTopPlayResult(ScoreWithBeatmapResult):
    username: str = ""


def _score_to_result(score: ScoreData) -> ScoreResult:
    return ScoreResult(
        id=score.id,
        beatmap_md5=score.beatmap_md5,
        player_id=score.player_id,
        score=score.score,
        max_combo=score.max_combo,
        full_combo=score.full_combo,
        mods=score.mods,
        count_300=score.count_300,
        count_100=score.count_100,
        count_50=score.count_50,
        count_katus=score.count_katus,
        count_gekis=score.count_gekis,
        count_misses=score.count_misses,
        submitted_at=score.submitted_at,
        play_mode=score.play_mode,
        completed=score.completed,
        accuracy=score.accuracy,
        pp=score.pp,
        playtime=score.playtime,
    )


def _score_with_beatmap_to_result(score: ScoreWithBeatmap) -> ScoreWithBeatmapResult:
    return ScoreWithBeatmapResult(
        id=score.id,
        beatmap_md5=score.beatmap_md5,
        player_id=score.player_id,
        score=score.score,
        max_combo=score.max_combo,
        full_combo=score.full_combo,
        mods=score.mods,
        count_300=score.count_300,
        count_100=score.count_100,
        count_50=score.count_50,
        count_katus=score.count_katus,
        count_gekis=score.count_gekis,
        count_misses=score.count_misses,
        submitted_at=score.submitted_at,
        play_mode=score.play_mode,
        completed=score.completed,
        accuracy=score.accuracy,
        pp=score.pp,
        playtime=score.playtime,
        beatmap_id=score.beatmap_id,
        beatmapset_id=score.beatmapset_id,
        song_name=score.song_name,
        difficulty=score.difficulty,
        ranked=score.ranked,
    )


async def get_score(
    ctx: AbstractContext,
    score_id: int,
    custom_mode: int = 0,
) -> ScoreError.OnSuccess[ScoreResult]:
    score = await ctx.scores.find_by_id(score_id, custom_mode)
    if not score:
        return ScoreError.SCORE_NOT_FOUND

    return _score_to_result(score)


async def get_player_best(
    ctx: AbstractContext,
    player_id: int,
    mode: int = 0,
    custom_mode: int = 0,
    page: int = 1,
    limit: int = 50,
) -> ScoreError.OnSuccess[list[ScoreWithBeatmapResult]]:
    user = await ctx.users.find_by_id(player_id)
    if not user:
        return ScoreError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return ScoreError.USER_RESTRICTED

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    scores = await ctx.scores.list_player_best(
        player_id,
        mode,
        custom_mode,
        limit,
        offset,
    )
    return [_score_with_beatmap_to_result(s) for s in scores]


async def get_player_recent(
    ctx: AbstractContext,
    player_id: int,
    mode: int = 0,
    custom_mode: int = 0,
    page: int = 1,
    limit: int = 50,
) -> ScoreError.OnSuccess[list[ScoreWithBeatmapResult]]:
    user = await ctx.users.find_by_id(player_id)
    if not user:
        return ScoreError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return ScoreError.USER_RESTRICTED

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    scores = await ctx.scores.list_player_recent(
        player_id,
        mode,
        custom_mode,
        limit,
        offset,
    )
    return [_score_with_beatmap_to_result(s) for s in scores]


async def get_player_firsts(
    ctx: AbstractContext,
    player_id: int,
    mode: int = 0,
    custom_mode: int = 0,
    page: int = 1,
    limit: int = 50,
) -> ScoreError.OnSuccess[list[ScoreWithBeatmapResult]]:
    user = await ctx.users.find_by_id(player_id)
    if not user:
        return ScoreError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return ScoreError.USER_RESTRICTED

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    scores = await ctx.scores.list_player_firsts(
        player_id,
        mode,
        custom_mode,
        limit,
        offset,
    )
    return [_score_with_beatmap_to_result(s) for s in scores]


async def get_player_pinned(
    ctx: AbstractContext,
    player_id: int,
    mode: int = 0,
    custom_mode: int = 0,
    page: int = 1,
    limit: int = 50,
) -> ScoreError.OnSuccess[list[ScoreWithBeatmapResult]]:
    user = await ctx.users.find_by_id(player_id)
    if not user:
        return ScoreError.USER_NOT_FOUND

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return ScoreError.USER_RESTRICTED

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    scores = await ctx.scores.list_player_pinned(
        player_id,
        mode,
        custom_mode,
        limit,
        offset,
    )
    return [_score_with_beatmap_to_result(s) for s in scores]


def _top_play_to_result(score: ScoreTopPlay) -> ScoreTopPlayResult:
    return ScoreTopPlayResult(
        id=score.id,
        beatmap_md5=score.beatmap_md5,
        player_id=score.player_id,
        score=score.score,
        max_combo=score.max_combo,
        full_combo=score.full_combo,
        mods=score.mods,
        count_300=score.count_300,
        count_100=score.count_100,
        count_50=score.count_50,
        count_katus=score.count_katus,
        count_gekis=score.count_gekis,
        count_misses=score.count_misses,
        submitted_at=score.submitted_at,
        play_mode=score.play_mode,
        completed=score.completed,
        accuracy=score.accuracy,
        pp=score.pp,
        playtime=score.playtime,
        beatmap_id=score.beatmap_id,
        beatmapset_id=score.beatmapset_id,
        song_name=score.song_name,
        difficulty=score.difficulty,
        ranked=score.ranked,
        username=score.username,
    )


async def get_top_plays(
    ctx: AbstractContext,
    mode: int = 0,
    custom_mode: int = 0,
    page: int = 1,
    limit: int = 50,
) -> ScoreError.OnSuccess[list[ScoreTopPlayResult]]:
    if not is_valid_mode(mode):
        return ScoreError.INVALID_MODE

    if not is_valid_custom_mode(custom_mode):
        return ScoreError.INVALID_CUSTOM_MODE

    if limit > 100:
        limit = 100
    offset = (page - 1) * limit

    top_scores = await ctx.scores.list_top_plays(mode, custom_mode, limit, offset)
    return [_top_play_to_result(s) for s in top_scores]


async def pin_score(
    ctx: AbstractContext,
    player_id: int,
    score_id: int,
    custom_mode: int = 0,
) -> ScoreError.OnSuccess[None]:
    score = await ctx.scores.find_by_id(score_id, custom_mode)
    if not score:
        return ScoreError.SCORE_NOT_FOUND

    if score.player_id != player_id:
        return ScoreError.NOT_YOUR_SCORE

    if await ctx.scores.is_pinned(player_id, score_id):
        return ScoreError.ALREADY_PINNED

    await ctx.scores.pin_score(player_id, score_id)
    return None


async def unpin_score(
    ctx: AbstractContext,
    player_id: int,
    score_id: int,
) -> ScoreError.OnSuccess[None]:
    if not await ctx.scores.is_pinned(player_id, score_id):
        return ScoreError.NOT_PINNED

    await ctx.scores.unpin_score(player_id, score_id)
    return None
