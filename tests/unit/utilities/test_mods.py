"""Unit tests for mods utilities."""

from __future__ import annotations

from soumetsu_api.utilities.mods import Mod
from soumetsu_api.utilities.mods import OsuMods
from soumetsu_api.utilities.mods import mods_from_score


class TestModsFromScore:
    """Tests for mods_from_score conversion."""

    def test_no_mods_returns_classic_only(self) -> None:
        result = mods_from_score(0, 1.0)

        assert result == [Mod(acronym="CL")]

    def test_single_non_speed_mod_has_no_settings(self) -> None:
        result = mods_from_score(int(OsuMods.HD), 1.0)

        assert result == [Mod(acronym="CL"), Mod(acronym="HD")]
        assert result[1].settings is None

    def test_doubletime_carries_speed_settings(self) -> None:
        result = mods_from_score(int(OsuMods.DT), 1.5)

        assert result == [
            Mod(acronym="CL"),
            Mod(
                acronym="DT",
                settings={"speed_change": 1.5, "adjust_pitch": False},
            ),
        ]

    def test_halftime_carries_speed_settings(self) -> None:
        result = mods_from_score(int(OsuMods.HT), 0.75)

        assert result == [
            Mod(acronym="CL"),
            Mod(
                acronym="HT",
                settings={"speed_change": 0.75, "adjust_pitch": False},
            ),
        ]

    def test_nightcore_suppresses_doubletime(self) -> None:
        # On stable, NC implies DT in the bitmask. Only NC should be
        # emitted in the output, with adjust_pitch=True.
        bitmask = int(OsuMods.NC | OsuMods.DT)

        result = mods_from_score(bitmask, 1.5)

        assert result == [
            Mod(acronym="CL"),
            Mod(
                acronym="NC",
                settings={"speed_change": 1.5, "adjust_pitch": True},
            ),
        ]

    def test_combined_mods_emit_in_bit_order(self) -> None:
        bitmask = int(OsuMods.HD | OsuMods.HR | OsuMods.DT)

        result = mods_from_score(bitmask, 1.5)

        acronyms = [m.acronym for m in result]
        assert acronyms == ["CL", "HD", "HR", "DT"]
        assert result[1].settings is None
        assert result[2].settings is None
        assert result[3].settings == {
            "speed_change": 1.5,
            "adjust_pitch": False,
        }

    def test_speed_change_is_rounded_to_two_decimals(self) -> None:
        result = mods_from_score(int(OsuMods.DT), 1.333)

        assert result[1].settings == {
            "speed_change": 1.33,
            "adjust_pitch": False,
        }
