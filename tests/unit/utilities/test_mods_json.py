from soumetsu_api.resources.scores import ScoreData
from soumetsu_api.utilities.mods import Mod
from soumetsu_api.utilities.mods import mods_from_score

ROW = dict(
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
)


def test_falls_back_to_the_mod_bits_without_a_json_list():
    mods = mods_from_score(1 << 3, 1.0)

    assert [m.acronym for m in mods] == ["CL", "HD"]


def test_prefers_the_patchers_own_list():
    stored = [Mod(acronym="DT", settings={"speed_change": 1.3})]

    assert mods_from_score(1 << 6, 1.5, stored) == stored


def test_score_data_decodes_the_driver_text():
    score = ScoreData(**ROW, mods_json='[{"acronym": "DT", "settings": {"speed_change": 1.3}}]')

    assert score.mods_json == [Mod(acronym="DT", settings={"speed_change": 1.3})]


def test_score_data_without_a_mod_list():
    assert ScoreData(**ROW, mods_json=None).mods_json is None
    assert ScoreData(**ROW).mods_json is None
