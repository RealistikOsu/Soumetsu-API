from soumetsu_api.resources.scores import ScoreData
from soumetsu_api.resources.scores import ScoreTopPlay
from soumetsu_api.resources.scores import ScoreTopPlayWithMode
from soumetsu_api.resources.scores import ScoreWithBeatmap
from soumetsu_api.services import scores
from soumetsu_api.utilities.mods import Mod

STORED = '[{"acronym": "DT", "settings": {"speed_change": 1.3}}]'
EXPECTED = [Mod(acronym="DT", settings={"speed_change": 1.3})]

SCORE = dict(
    id=1,
    beatmap_md5="x",
    player_id=2,
    score=5_000_000_000,
    max_combo=1,
    full_combo=True,
    mods=64,
    count_300=1,
    count_100=0,
    count_50=0,
    count_katus=0,
    count_gekis=0,
    count_misses=0,
    submitted_at=1,
    play_mode=0,
    completed=3,
    accuracy=100.0,
    pp=1.0,
    playtime=1,
    playback_rate=1.3,
    mods_json=STORED,
)
BEATMAP = dict(beatmap_id=3, beatmapset_id=4, song_name="s", difficulty=5.0, ranked=2)


def test_every_result_keeps_the_mod_list():
    plain = scores._score_to_result(ScoreData(**SCORE))
    with_beatmap = scores.score_with_beatmap_to_result(
        ScoreWithBeatmap(**SCORE, **BEATMAP),
    )
    top = scores._top_play_to_result(ScoreTopPlay(**SCORE, **BEATMAP, username="u"))
    top_mode = scores._top_play_with_mode_to_result(
        ScoreTopPlayWithMode(**SCORE, **BEATMAP, username="u", custom_mode=1),
    )

    for result in (plain, with_beatmap, top, top_mode):
        assert result.mods_json == EXPECTED


def test_results_without_a_mod_list():
    result = scores._score_to_result(ScoreData(**{**SCORE, "mods_json": None}))

    assert result.mods_json is None
