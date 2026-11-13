import json

from soumetsu_api.utilities.mods import mods_from_score


def test_falls_back_to_the_mod_bits_without_a_json_list():
    mods = mods_from_score(1 << 3, 1.0)

    assert [m.acronym for m in mods] == ["CL", "HD"]


def test_prefers_the_patchers_own_list():
    blob = json.dumps(
        {
            "mods": [
                {"acronym": "CL", "settings": {}},
                {"acronym": "DT", "settings": {"speed_change": 1.3}},
            ]
        }
    )

    mods = mods_from_score(1 << 6, 1.5, blob)

    assert [m.acronym for m in mods] == ["CL", "DT"]
    assert mods[0].settings is None
    assert mods[1].settings == {"speed_change": 1.3}


def test_a_broken_list_falls_back_to_the_mod_bits():
    mods = mods_from_score(1 << 3, 1.0, "not json")

    assert [m.acronym for m in mods] == ["CL", "HD"]
