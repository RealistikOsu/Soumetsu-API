from __future__ import annotations

import json
from typing import Any

from soumetsu_api.utilities.mods import MOD_ACRONYMS

# Stable's mod bit for each acronym; lazer-only mods have none and are left out.
_MOD_BITS = {acronym: 1 << index for index, acronym in enumerate(MOD_ACRONYMS)}


def _mods(raw: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
    return json.loads(raw) if isinstance(raw, str) else raw


def legacy_mod_bits(raw_mods: str | list[dict[str, Any]]) -> int:
    return sum(_MOD_BITS.get(mod["acronym"], 0) for mod in _mods(raw_mods))


def playback_rate(raw_mods: str | list[dict[str, Any]]) -> float:
    defaults = {"DT": 1.5, "NC": 1.5, "HT": 0.75, "DC": 0.75}
    for mod in _mods(raw_mods):
        if mod["acronym"] in defaults:
            return float(
                (mod.get("settings") or {}).get(
                    "speed_change", defaults[mod["acronym"]]
                )
            )

    return 1.0


def legacy_counts(
    ruleset_id: int, raw_statistics: str | dict[str, int]
) -> dict[str, int]:
    """Lazer hit results as stable's count columns, for showing a lazer score like any other."""
    stats = (
        json.loads(raw_statistics)
        if isinstance(raw_statistics, str)
        else raw_statistics
    )
    hit = stats.get

    if ruleset_id == 2:
        return {
            "count_300": hit("great", 0),
            "count_100": hit("large_tick_hit", 0),
            "count_50": hit("small_tick_hit", 0),
            "count_katus": hit("small_tick_miss", 0),
            "count_gekis": 0,
            "count_misses": hit("miss", 0) + hit("large_tick_miss", 0),
        }

    if ruleset_id == 3:
        return {
            "count_300": hit("great", 0),
            "count_100": hit("ok", 0),
            "count_50": hit("meh", 0),
            "count_katus": hit("good", 0),
            "count_gekis": hit("perfect", 0),
            "count_misses": hit("miss", 0),
        }

    return {
        "count_300": hit("great", 0),
        "count_100": hit("ok", 0),
        "count_50": hit("meh", 0),
        "count_katus": 0,
        "count_gekis": 0,
        "count_misses": hit("miss", 0),
    }
