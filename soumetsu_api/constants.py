"""Centralized constants for Soumetsu API."""

from __future__ import annotations

from enum import IntEnum


class GameMode(IntEnum):
    """osu! game modes."""

    STD = 0
    TAIKO = 1
    CTB = 2
    MANIA = 3


class CustomMode(IntEnum):
    """Custom game modes (vanilla, relax, autopilot)."""

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

# Level calculation constants
LEVEL_100_THRESHOLD = 100
MAX_LEVEL = 120
LEVEL_BASE_SCORE = 5000
LEVEL_HIGH_MULTIPLIER = 1.8
LEVEL_HIGH_BASE = 60
LEVEL_100_SCORE = 26931190829
LEVEL_100_INCREMENT = 100000000000


def combined_mode(mode: int, custom_mode: int) -> int:
    """Clean-schema mode 0-7: vanilla std/taiko/ctb/mania=0-3,
    relax std/taiko/ctb=4-6, autopilot std=7."""
    if custom_mode == CustomMode.AUTOPILOT:
        return 7
    if custom_mode == CustomMode.RELAX:
        return 4 + mode
    return mode


def is_valid_mode(mode: int) -> bool:
    """Check if mode is a valid game mode (0-3)."""
    return 0 <= mode <= 3


def is_valid_custom_mode(custom_mode: int) -> bool:
    """Check if custom mode is valid (0-2)."""
    return 0 <= custom_mode <= 2


def get_mode_suffix(mode: int) -> str:
    """Get the mode suffix string (used for redis leaderboard keys)."""
    return MODE_SUFFIXES[mode]
