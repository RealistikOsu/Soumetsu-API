"""Centralized constants for Soumetsu API."""

from __future__ import annotations

from enum import IntEnum


class GameMode(IntEnum):
    """osu! game modes."""

    STD = 0
    TAIKO = 1
    CTB = 2
    MANIA = 3


class Playstyle(IntEnum):
    """Score playstyles (vanilla, relax, autopilot)."""

    VANILLA = 0
    RELAX = 1
    AUTOPILOT = 2


# Database column suffixes for mode-specific stats
MODE_SUFFIXES: dict[int, str] = {
    GameMode.STD: "std",
    GameMode.TAIKO: "taiko",
    GameMode.CTB: "ctb",
    GameMode.MANIA: "mania",
}

# Database table names for playstyle-specific stats
STATS_TABLES: dict[int, str] = {
    Playstyle.VANILLA: "users_stats",
    Playstyle.RELAX: "rx_stats",
    Playstyle.AUTOPILOT: "ap_stats",
}

# Level calculation constants
LEVEL_100_THRESHOLD = 100
MAX_LEVEL = 120
LEVEL_BASE_SCORE = 5000
LEVEL_HIGH_MULTIPLIER = 1.8
LEVEL_HIGH_BASE = 60
LEVEL_100_SCORE = 26931190829
LEVEL_100_INCREMENT = 100000000000


def is_valid_mode(mode: int) -> bool:
    """Check if mode is a valid game mode (0-3)."""
    return 0 <= mode <= 3


def is_valid_playstyle(playstyle: int) -> bool:
    """Check if playstyle is valid (0-2)."""
    return 0 <= playstyle <= 2


def get_mode_suffix(mode: int) -> str:
    """Get the database column suffix for a game mode."""
    return MODE_SUFFIXES[mode]


def get_stats_table(playstyle: int) -> str:
    """Get the database table name for a playstyle."""
    return STATS_TABLES[playstyle]
