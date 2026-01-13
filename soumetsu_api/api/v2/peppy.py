from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query
from fastapi.responses import JSONResponse

from soumetsu_api.api.v2.context import RequiresContext
from soumetsu_api.utilities import privileges

router = APIRouter(prefix="/peppy")


def _mode_from_param(m: int | None) -> int:
    if m is None or m < 0 or m > 3:
        return 0
    return m


@router.get("/get_user")
async def get_user(
    ctx: RequiresContext,
    k: str = Query(...),
    u: str | None = Query(None),
    m: int | None = Query(None),
    type: str | None = Query(None),
) -> JSONResponse:
    if not u:
        return JSONResponse([])

    mode = _mode_from_param(m)

    if type == "id" or u.isdigit():
        user = await ctx.users.find_by_id(int(u))
    else:
        user = await ctx.users.find_by_username(u)

    if not user:
        return JSONResponse([])

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return JSONResponse([])

    stats = await ctx.user_stats.get_stats(user.id, mode, 0)
    global_rank = await ctx.user_stats.get_global_rank(user.id, mode, 0)

    return JSONResponse(
        [
            {
                "user_id": str(user.id),
                "username": user.username,
                "join_date": str(user.register_datetime),
                "count300": str(stats.total_hits if stats else 0),
                "count100": "0",
                "count50": "0",
                "playcount": str(stats.playcount if stats else 0),
                "ranked_score": str(stats.ranked_score if stats else 0),
                "total_score": str(stats.total_score if stats else 0),
                "pp_rank": str(global_rank),
                "level": str(stats.level if stats else 1),
                "pp_raw": str(stats.pp if stats else 0),
                "accuracy": str(stats.accuracy if stats else 0),
                "count_rank_ss": "0",
                "count_rank_ssh": "0",
                "count_rank_s": "0",
                "count_rank_sh": "0",
                "count_rank_a": "0",
                "country": user.country,
                "total_seconds_played": str(stats.playtime if stats else 0),
                "pp_country_rank": "0",
                "events": [],
            },
        ],
    )


@router.get("/get_beatmaps")
async def get_beatmaps(
    ctx: RequiresContext,
    k: str = Query(...),
    b: int | None = Query(None),
    s: int | None = Query(None),
    h: str | None = Query(None),
    m: int | None = Query(None),
    limit: int = Query(500),
) -> JSONResponse:
    if b:
        beatmap = await ctx.beatmaps.get_by_id(b)
        if not beatmap:
            return JSONResponse([])

        return JSONResponse(
            [
                {
                    "beatmap_id": str(beatmap.beatmap_id),
                    "beatmapset_id": str(beatmap.beatmapset_id),
                    "approved": str(beatmap.ranked),
                    "total_length": str(beatmap.hit_length),
                    "hit_length": str(beatmap.hit_length),
                    "version": "",
                    "file_md5": beatmap.beatmap_md5,
                    "diff_size": "0",
                    "diff_overall": str(beatmap.od),
                    "diff_approach": str(beatmap.ar),
                    "diff_drain": "0",
                    "mode": str(beatmap.mode),
                    "count_normal": "0",
                    "count_slider": "0",
                    "count_spinner": "0",
                    "submit_date": "",
                    "approved_date": "",
                    "last_update": str(beatmap.latest_update),
                    "artist": "",
                    "artist_unicode": "",
                    "title": beatmap.song_name,
                    "title_unicode": "",
                    "creator": "",
                    "creator_id": str(beatmap.mapper_id),
                    "bpm": str(beatmap.bpm),
                    "source": "",
                    "tags": "",
                    "genre_id": "0",
                    "language_id": "0",
                    "favourite_count": "0",
                    "rating": "0",
                    "storyboard": "0",
                    "video": "0",
                    "download_unavailable": "0",
                    "audio_unavailable": "0",
                    "playcount": str(beatmap.playcount),
                    "passcount": str(beatmap.passcount),
                    "packs": "",
                    "max_combo": str(beatmap.max_combo),
                    "diff_aim": "0",
                    "diff_speed": "0",
                    "difficultyrating": str(beatmap.difficulty_std),
                },
            ],
        )

    if h:
        beatmap = await ctx.beatmaps.get_by_md5(h)
        if not beatmap:
            return JSONResponse([])

        return JSONResponse(
            [
                {
                    "beatmap_id": str(beatmap.beatmap_id),
                    "beatmapset_id": str(beatmap.beatmapset_id),
                    "approved": str(beatmap.ranked),
                    "total_length": str(beatmap.hit_length),
                    "hit_length": str(beatmap.hit_length),
                    "version": "",
                    "file_md5": beatmap.beatmap_md5,
                    "diff_size": "0",
                    "diff_overall": str(beatmap.od),
                    "diff_approach": str(beatmap.ar),
                    "diff_drain": "0",
                    "mode": str(beatmap.mode),
                    "count_normal": "0",
                    "count_slider": "0",
                    "count_spinner": "0",
                    "submit_date": "",
                    "approved_date": "",
                    "last_update": str(beatmap.latest_update),
                    "artist": "",
                    "artist_unicode": "",
                    "title": beatmap.song_name,
                    "title_unicode": "",
                    "creator": "",
                    "creator_id": str(beatmap.mapper_id),
                    "bpm": str(beatmap.bpm),
                    "source": "",
                    "tags": "",
                    "genre_id": "0",
                    "language_id": "0",
                    "favourite_count": "0",
                    "rating": "0",
                    "storyboard": "0",
                    "video": "0",
                    "download_unavailable": "0",
                    "audio_unavailable": "0",
                    "playcount": str(beatmap.playcount),
                    "passcount": str(beatmap.passcount),
                    "packs": "",
                    "max_combo": str(beatmap.max_combo),
                    "diff_aim": "0",
                    "diff_speed": "0",
                    "difficultyrating": str(beatmap.difficulty_std),
                },
            ],
        )

    if s:
        beatmaps = await ctx.beatmaps.get_beatmapset(s)
        return JSONResponse(
            [
                {
                    "beatmap_id": str(b.beatmap_id),
                    "beatmapset_id": str(b.beatmapset_id),
                    "approved": str(b.ranked),
                    "total_length": str(b.hit_length),
                    "hit_length": str(b.hit_length),
                    "version": "",
                    "file_md5": b.beatmap_md5,
                    "diff_size": "0",
                    "diff_overall": str(b.od),
                    "diff_approach": str(b.ar),
                    "diff_drain": "0",
                    "mode": str(b.mode),
                    "title": b.song_name,
                    "bpm": str(b.bpm),
                    "creator_id": str(b.mapper_id),
                    "playcount": str(b.playcount),
                    "passcount": str(b.passcount),
                    "max_combo": str(b.max_combo),
                    "difficultyrating": str(b.difficulty_std),
                }
                for b in beatmaps
            ],
        )

    return JSONResponse([])


@router.get("/get_scores")
async def get_scores(
    ctx: RequiresContext,
    k: str = Query(...),
    b: int = Query(...),
    m: int | None = Query(None),
    limit: int = Query(50),
) -> JSONResponse:
    mode = _mode_from_param(m)

    beatmap = await ctx.beatmaps.get_by_id(b)
    if not beatmap:
        return JSONResponse([])

    scores = await ctx.scores.get_beatmap_scores(beatmap.beatmap_md5, mode, 0, limit, 0)

    result = []
    for s in scores:
        user = await ctx.users.find_by_id(s.user_id)
        result.append(
            {
                "score_id": str(s.id),
                "score": str(s.score),
                "username": user.username if user else "Unknown",
                "count300": str(s.count_300),
                "count100": str(s.count_100),
                "count50": str(s.count_50),
                "countmiss": str(s.count_misses),
                "maxcombo": str(s.max_combo),
                "countkatu": str(s.count_katus),
                "countgeki": str(s.count_gekis),
                "perfect": "1" if s.full_combo else "0",
                "enabled_mods": str(s.mods),
                "user_id": str(s.user_id),
                "date": s.time,
                "rank": "",
                "pp": str(s.pp),
                "replay_available": "0",
            },
        )

    return JSONResponse(result)


@router.get("/get_user_best")
async def get_user_best(
    ctx: RequiresContext,
    k: str = Query(...),
    u: str = Query(...),
    m: int | None = Query(None),
    limit: int = Query(10),
    type: str | None = Query(None),
) -> JSONResponse:
    mode = _mode_from_param(m)

    if type == "id" or u.isdigit():
        user = await ctx.users.find_by_id(int(u))
    else:
        user = await ctx.users.find_by_username(u)

    if not user:
        return JSONResponse([])

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return JSONResponse([])

    scores = await ctx.scores.get_user_best(user.id, mode, 0, min(limit, 100), 0)

    return JSONResponse(
        [
            {
                "beatmap_id": str(s.beatmap_id),
                "score_id": str(s.id),
                "score": str(s.score),
                "maxcombo": str(s.max_combo),
                "count50": str(s.count_50),
                "count100": str(s.count_100),
                "count300": str(s.count_300),
                "countmiss": str(s.count_misses),
                "countkatu": str(s.count_katus),
                "countgeki": str(s.count_gekis),
                "perfect": "1" if s.full_combo else "0",
                "enabled_mods": str(s.mods),
                "user_id": str(user.id),
                "date": s.time,
                "rank": "",
                "pp": str(s.pp),
                "replay_available": "0",
            }
            for s in scores
        ],
    )


@router.get("/get_user_recent")
async def get_user_recent(
    ctx: RequiresContext,
    k: str = Query(...),
    u: str = Query(...),
    m: int | None = Query(None),
    limit: int = Query(10),
    type: str | None = Query(None),
) -> JSONResponse:
    mode = _mode_from_param(m)

    if type == "id" or u.isdigit():
        user = await ctx.users.find_by_id(int(u))
    else:
        user = await ctx.users.find_by_username(u)

    if not user:
        return JSONResponse([])

    user_privs = privileges.UserPrivileges(user.privileges)
    if privileges.is_restricted(user_privs):
        return JSONResponse([])

    scores = await ctx.scores.get_user_recent(user.id, mode, 0, min(limit, 50), 0)

    return JSONResponse(
        [
            {
                "beatmap_id": str(s.beatmap_id),
                "score_id": str(s.id),
                "score": str(s.score),
                "maxcombo": str(s.max_combo),
                "count50": str(s.count_50),
                "count100": str(s.count_100),
                "count300": str(s.count_300),
                "countmiss": str(s.count_misses),
                "countkatu": str(s.count_katus),
                "countgeki": str(s.count_gekis),
                "perfect": "1" if s.full_combo else "0",
                "enabled_mods": str(s.mods),
                "user_id": str(user.id),
                "date": s.time,
                "rank": "",
                "pp": str(s.pp),
                "replay_available": "0",
            }
            for s in scores
        ],
    )


@router.get("/get_match")
async def get_match(
    ctx: RequiresContext,
    k: str = Query(...),
    mp: int = Query(...),
) -> JSONResponse:
    # Multiplayer matches are not implemented in this API
    return JSONResponse({"match": 0, "games": []})
