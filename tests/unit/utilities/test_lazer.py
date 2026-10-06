"""Unit tests for the osu!lazer score conversions."""

from __future__ import annotations

from soumetsu_api.utilities import lazer
from soumetsu_api.utilities.mods import OsuMods


class TestLegacyModBits:
    def test_known_mods_map_to_stable_bits(self) -> None:
        mods = [{"acronym": "HD"}, {"acronym": "DT", "settings": {"speed_change": 1.2}}]

        assert lazer.legacy_mod_bits(mods) == OsuMods.HD | OsuMods.DT

    def test_lazer_only_mods_are_left_out(self) -> None:
        assert lazer.legacy_mod_bits([{"acronym": "CL"}, {"acronym": "AS"}]) == 0

    def test_accepts_the_stored_json(self) -> None:
        assert lazer.legacy_mod_bits('[{"acronym": "HR"}]') == OsuMods.HR


class TestPlaybackRate:
    def test_no_rate_mod_is_normal_speed(self) -> None:
        assert lazer.playback_rate([{"acronym": "HD"}]) == 1.0

    def test_default_rates(self) -> None:
        assert lazer.playback_rate([{"acronym": "DT"}]) == 1.5
        assert lazer.playback_rate([{"acronym": "NC"}]) == 1.5
        assert lazer.playback_rate([{"acronym": "HT"}]) == 0.75

    def test_custom_speed_change_wins(self) -> None:
        mods = [{"acronym": "DT", "settings": {"speed_change": 1.25}}]

        assert lazer.playback_rate(mods) == 1.25


class TestLegacyCounts:
    def test_osu(self) -> None:
        counts = lazer.legacy_counts(0, {"great": 400, "ok": 12, "meh": 3, "miss": 2})

        assert counts == {
            "count_300": 400,
            "count_100": 12,
            "count_50": 3,
            "count_katus": 0,
            "count_gekis": 0,
            "count_misses": 2,
        }

    def test_mania_uses_gekis_and_katus(self) -> None:
        counts = lazer.legacy_counts(
            3, {"perfect": 100, "great": 50, "good": 5, "ok": 2, "meh": 1, "miss": 4}
        )

        assert counts["count_gekis"] == 100
        assert counts["count_300"] == 50
        assert counts["count_katus"] == 5
        assert counts["count_100"] == 2
        assert counts["count_50"] == 1
        assert counts["count_misses"] == 4

    def test_catch_counts_missed_drops_as_misses(self) -> None:
        counts = lazer.legacy_counts(
            2,
            {
                "great": 100,
                "large_tick_hit": 20,
                "small_tick_hit": 50,
                "small_tick_miss": 3,
                "miss": 1,
                "large_tick_miss": 2,
            },
        )

        assert counts["count_300"] == 100
        assert counts["count_100"] == 20
        assert counts["count_50"] == 50
        assert counts["count_katus"] == 3
        assert counts["count_misses"] == 3

    def test_accepts_the_stored_json(self) -> None:
        assert lazer.legacy_counts(1, '{"great": 9}')["count_300"] == 9
