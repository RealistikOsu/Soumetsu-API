import json

from soumetsu_api.resources.scores import ScoreData
from soumetsu_api.utilities.mods import mods_from_score
from soumetsu_api.utilities.mods import parse_mods_json


def test_falls_back_to_the_mod_bits_without_a_json_list():
    mods = mods_from_score(1 << 3, 1.0)

    assert [m.acronym for m in mods] == ["CL", "HD"]


def test_prefers_the_patchers_own_list():
    blob = json.dumps(
        [
            {"acronym": "CL", "settings": {}},
            {"acronym": "DT", "settings": {"speed_change": 1.3}},
        ]
    )

    mods = mods_from_score(1 << 6, 1.5, blob)

    assert [m.acronym for m in mods] == ["CL", "DT"]
    assert mods[0].settings is None
    assert mods[1].settings == {"speed_change": 1.3}


def test_a_broken_list_falls_back_to_the_mod_bits():
    mods = mods_from_score(1 << 3, 1.0, "not json")

    assert [m.acronym for m in mods] == ["CL", "HD"]


def test_parse_mods_json_reads_driver_text_and_parsed_lists():
    mods = [{"acronym": "DT", "settings": {"speed_change": 1.3}}]

    assert parse_mods_json(json.dumps(mods)) == mods
    assert parse_mods_json(mods) == mods
    assert parse_mods_json(None) is None
    assert parse_mods_json("") is None
    assert parse_mods_json("not json") is None
    assert parse_mods_json('{"mods": []}') is None
    assert parse_mods_json('[{"settings": {}}]') is None


def test_score_data_takes_the_driver_text():
    row = dict(
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

    with_mods = ScoreData(**row, mods_json='[{"acronym": "DT", "settings": {"speed_change": 1.3}}]')
    without = ScoreData(**row, mods_json=None)

    assert with_mods.mods_json == [{"acronym": "DT", "settings": {"speed_change": 1.3}}]
    assert without.mods_json is None
