from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import BaseModel

from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.resources.beatmaps import BeatmapData
from soumetsu_api.utilities import privileges

router = APIRouter(prefix="/peppy")


# Peppy API returns all values as strings to match osu! API format
class PeppyUserResponse(BaseModel):
    user_id: str
    username: str
    join_date: str
    count300: str
    count100: str
    count50: str
    playcount: str
    ranked_score: str
    total_score: str
    pp_rank: str
    level: str
    pp_raw: str
    accuracy: str
    count_rank_ss: str
    count_rank_ssh: str
    count_rank_s: str
    count_rank_sh: str
    count_rank_a: str
    country: str
    total_seconds_played: str
    pp_country_rank: str
    events: list[str]


class PeppyBeatmapResponse(BaseModel):
    beatmap_id: str
    beatmapset_id: str
    approved: str
    total_length: str
    hit_length: str
    version: str
    file_md5: str
    diff_size: str
    diff_overall: str
    diff_approach: str
    diff_drain: str
    mode: str
    count_normal: str
    count_slider: str
    count_spinner: str
    submit_date: str
    approved_date: str
    last_update: str
    artist: str
    artist_unicode: str
    title: str
    title_unicode: str
    creator: str
    creator_id: str
    bpm: str
    source: str
    tags: str
    genre_id: str
    language_id: str
    favourite_count: str
    rating: str
    storyboard: str
    video: str
    download_unavailable: str
    audio_unavailable: str
    playcount: str
    passcount: str
    packs: str
    max_combo: str
    diff_aim: str
    diff_speed: str
    difficultyrating: str


class PeppyBeatmapCompactResponse(BaseModel):
    beatmap_id: str
    beatmapset_id: str
    approved: str
    total_length: str
    hit_length: str
    version: str
    file_md5: str
    diff_size: str
    diff_overall: str
    diff_approach: str
    diff_drain: str
    mode: str
    title: str
    bpm: str
    creator_id: str
    playcount: str
    passcount: str
    max_combo: str
    difficultyrating: str


class PeppyScoreResponse(BaseModel):
    score_id: str
    score: str
    username: str
    count300: str
    count100: str
    count50: str
    countmiss: str
    maxcombo: str
    countkatu: str
    countgeki: str
    perfect: str
    enabled_mods: str
    user_id: str
    date: str
    rank: str
    pp: str
    replay_available: str


class PeppyUserScoreResponse(BaseModel):
    beatmap_id: str
    score_id: str
    score: str
    maxcombo: str
    count50: str
    count100: str
    count300: str
    countmiss: str
    countkatu: str
    countgeki: str
    perfect: str
    enabled_mods: str
    user_id: str
    date: str
    rank: str
    pp: str
    replay_available: str


class PeppyMatchResponse(BaseModel):
    match: int
    games: list[str]


def _mode_from_param(m: int | None) -> int:
    if m is None or m < 0 or m > 3:
        return 0
    return m


def _beatmap_to_full_response(beatmap: BeatmapData) -> PeppyBeatmapResponse:
    return PeppyBeatmapResponse(
        beatmap_id=str(beatmap.beatmap_id),
        beatmapset_id=str(beatmap.beatmapset_id),
        approved=str(beatmap.ranked),
        total_length=str(beatmap.hit_length),
        hit_length=str(beatmap.hit_length),
        version="",
        file_md5=beatmap.beatmap_md5,
        diff_size="0",
        diff_overall=str(beatmap.od),
        diff_approach=str(beatmap.ar),
        diff_drain="0",
        mode=str(beatmap.mode),
        count_normal="0",
        count_slider="0",
        count_spinner="0",
        submit_date="",
        approved_date="",
        last_update=str(beatmap.latest_update),
        artist="",
        artist_unicode="",
        title=beatmap.song_name,
        title_unicode="",
        creator="",
        creator_id=str(beatmap.mapper_id),
        bpm=str(beatmap.bpm),
        source="",
        tags="",
        genre_id="0",
        language_id="0",
        favourite_count="0",
        rating="0",
        storyboard="0",
        video="0",
        download_unavailable="0",
        audio_unavailable="0",
        playcount=str(beatmap.playcount),
        passcount=str(beatmap.passcount),
        packs="",
        max_combo=str(beatmap.max_combo),
        diff_aim="0",
        diff_speed="0",
        difficultyrating=str(beatmap.difficulty_std),
    )


def _beatmap_to_compact_response(beatmap: BeatmapData) -> PeppyBeatmapCompactResponse:
    return PeppyBeatmapCompactResponse(
        beatmap_id=str(beatmap.beatmap_id),
        beatmapset_id=str(beatmap.beatmapset_id),
        approved=str(beatmap.ranked),
        total_length=str(beatmap.hit_length),
        hit_length=str(beatmap.hit_length),
        version="",
        file_md5=beatmap.beatmap_md5,
        diff_size="0",
        diff_overall=str(beatmap.od),
        diff_approach=str(beatmap.ar),
        diff_drain="0",
        mode=str(beatmap.mode),
        title=beatmap.song_name,
        bpm=str(beatmap.bpm),
        creator_id=str(beatmap.mapper_id),
        playcount=str(beatmap.playcount),
        passcount=str(beatmap.passcount),
        max_combo=str(beatmap.max_combo),
        difficultyrating=str(beatmap.difficulty_std),
    )


@router.get("/get_user", response_model=list[PeppyUserResponse])
async def get_user(
    ctx: RequiresContext,
    k: str = Query(...),
    u: str | None = Query(None),
    m: int | None = Query(None),
    type: str | None = Query(None),
) -> Response:
    if not u:
        return Response(content="[]", media_type="application/json")

    mode = _mode_from_param(m)

    if type == "id" or u.isdigit():
        user = await ctx.users.find_by_id(int(u))
    else:
        user = await ctx.users.find_by_username(u)

    if not user:
        return Response(content="[]", media_type="application/json")

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return Response(content="[]", media_type="application/json")

    stats = await ctx.user_stats.get_stats(user.id, mode, 0)
    global_rank = await ctx.leaderboard.get_user_global_rank(user.id, mode, 0)

    result = [
        PeppyUserResponse(
            user_id=str(user.id),
            username=user.username,
            join_date=str(user.register_datetime),
            count300=str(stats.total_hits if stats else 0),
            count100="0",
            count50="0",
            playcount=str(stats.playcount if stats else 0),
            ranked_score=str(stats.ranked_score if stats else 0),
            total_score=str(stats.total_score if stats else 0),
            pp_rank=str(global_rank),
            level=str(stats.level if stats else 1),
            pp_raw=str(stats.pp if stats else 0),
            accuracy=str(stats.accuracy if stats else 0),
            count_rank_ss="0",
            count_rank_ssh="0",
            count_rank_s="0",
            count_rank_sh="0",
            count_rank_a="0",
            country=user.country,
            total_seconds_played=str(stats.playtime if stats else 0),
            pp_country_rank="0",
            events=[],
        ),
    ]

    return Response(
        content=f"[{result[0].model_dump_json()}]",
        media_type="application/json",
    )


@router.get("/get_beatmaps", response_model=list[PeppyBeatmapResponse])
async def get_beatmaps(
    ctx: RequiresContext,
    k: str = Query(...),
    b: int | None = Query(None),
    s: int | None = Query(None),
    h: str | None = Query(None),
    m: int | None = Query(None),
    limit: int = Query(500),
) -> Response:
    if b:
        beatmap = await ctx.beatmaps.find_by_id(b)
        if not beatmap:
            return Response(content="[]", media_type="application/json")

        result = _beatmap_to_full_response(beatmap)
        return Response(
            content=f"[{result.model_dump_json()}]",
            media_type="application/json",
        )

    if h:
        beatmap = await ctx.beatmaps.find_by_md5(h)
        if not beatmap:
            return Response(content="[]", media_type="application/json")

        result = _beatmap_to_full_response(beatmap)
        return Response(
            content=f"[{result.model_dump_json()}]",
            media_type="application/json",
        )

    if s:
        beatmaps = await ctx.beatmaps.list_beatmapset(s)
        results = [_beatmap_to_compact_response(bm) for bm in beatmaps]
        json_items = ",".join(r.model_dump_json() for r in results)
        return Response(
            content=f"[{json_items}]",
            media_type="application/json",
        )

    return Response(content="[]", media_type="application/json")


@router.get("/get_scores", response_model=list[PeppyScoreResponse])
async def get_scores(
    ctx: RequiresContext,
    k: str = Query(...),
    b: int = Query(...),
    m: int | None = Query(None),
    limit: int = Query(50),
) -> Response:
    mode = _mode_from_param(m)

    beatmap = await ctx.beatmaps.find_by_id(b)
    if not beatmap:
        return Response(content="[]", media_type="application/json")

    scores = await ctx.scores.list_beatmap_scores(
        beatmap.beatmap_md5,
        mode,
        0,
        limit,
        0,
    )

    results = []
    for s in scores:
        user = await ctx.users.find_by_id(s.player_id)
        results.append(
            PeppyScoreResponse(
                score_id=str(s.id),
                score=str(s.score),
                username=user.username if user else "Unknown",
                count300=str(s.count_300),
                count100=str(s.count_100),
                count50=str(s.count_50),
                countmiss=str(s.count_misses),
                maxcombo=str(s.max_combo),
                countkatu=str(s.count_katus),
                countgeki=str(s.count_gekis),
                perfect="1" if s.full_combo else "0",
                enabled_mods=str(s.mods),
                user_id=str(s.player_id),
                date=s.submitted_at,
                rank="",
                pp=str(s.pp),
                replay_available="0",
            ),
        )

    json_items = ",".join(r.model_dump_json() for r in results)
    return Response(
        content=f"[{json_items}]",
        media_type="application/json",
    )


@router.get("/get_user_best", response_model=list[PeppyUserScoreResponse])
async def get_user_best(
    ctx: RequiresContext,
    k: str = Query(...),
    u: str = Query(...),
    m: int | None = Query(None),
    limit: int = Query(10),
    type: str | None = Query(None),
) -> Response:
    mode = _mode_from_param(m)

    if type == "id" or u.isdigit():
        user = await ctx.users.find_by_id(int(u))
    else:
        user = await ctx.users.find_by_username(u)

    if not user:
        return Response(content="[]", media_type="application/json")

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return Response(content="[]", media_type="application/json")

    scores = await ctx.scores.list_player_best(user.id, mode, 0, min(limit, 100), 0)

    results = [
        PeppyUserScoreResponse(
            beatmap_id=str(s.beatmap_id),
            score_id=str(s.id),
            score=str(s.score),
            maxcombo=str(s.max_combo),
            count50=str(s.count_50),
            count100=str(s.count_100),
            count300=str(s.count_300),
            countmiss=str(s.count_misses),
            countkatu=str(s.count_katus),
            countgeki=str(s.count_gekis),
            perfect="1" if s.full_combo else "0",
            enabled_mods=str(s.mods),
            user_id=str(user.id),
            date=s.submitted_at,
            rank="",
            pp=str(s.pp),
            replay_available="0",
        )
        for s in scores
    ]

    json_items = ",".join(r.model_dump_json() for r in results)
    return Response(
        content=f"[{json_items}]",
        media_type="application/json",
    )


@router.get("/get_user_recent", response_model=list[PeppyUserScoreResponse])
async def get_user_recent(
    ctx: RequiresContext,
    k: str = Query(...),
    u: str = Query(...),
    m: int | None = Query(None),
    limit: int = Query(10),
    type: str | None = Query(None),
) -> Response:
    mode = _mode_from_param(m)

    if type == "id" or u.isdigit():
        user = await ctx.users.find_by_id(int(u))
    else:
        user = await ctx.users.find_by_username(u)

    if not user:
        return Response(content="[]", media_type="application/json")

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return Response(content="[]", media_type="application/json")

    scores = await ctx.scores.list_player_recent(user.id, mode, 0, min(limit, 50), 0)

    results = [
        PeppyUserScoreResponse(
            beatmap_id=str(s.beatmap_id),
            score_id=str(s.id),
            score=str(s.score),
            maxcombo=str(s.max_combo),
            count50=str(s.count_50),
            count100=str(s.count_100),
            count300=str(s.count_300),
            countmiss=str(s.count_misses),
            countkatu=str(s.count_katus),
            countgeki=str(s.count_gekis),
            perfect="1" if s.full_combo else "0",
            enabled_mods=str(s.mods),
            user_id=str(user.id),
            date=s.submitted_at,
            rank="",
            pp=str(s.pp),
            replay_available="0",
        )
        for s in scores
    ]

    json_items = ",".join(r.model_dump_json() for r in results)
    return Response(
        content=f"[{json_items}]",
        media_type="application/json",
    )


@router.get("/get_match", response_model=PeppyMatchResponse)
async def get_match(
    ctx: RequiresContext,
    k: str = Query(...),
    mp: int = Query(...),
) -> PeppyMatchResponse:
    # Multiplayer matches are not implemented in this API
    return PeppyMatchResponse(match=0, games=[])
