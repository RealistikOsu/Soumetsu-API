from __future__ import annotations

from soumetsu_api.utilities.mods import OsuMods

_SILVER_MODS = OsuMods.HD | OsuMods.FL


def _grade_from_ratios(c300: int, c50: int, misses: int, total: int) -> str:
    if total == 0:
        return "D"

    ratio300 = c300 / total
    ratio50 = c50 / total

    if ratio300 == 1:
        return "X"
    if ratio300 > 0.9 and ratio50 <= 0.01 and misses == 0:
        return "S"
    if (ratio300 > 0.8 and misses == 0) or ratio300 > 0.9:
        return "A"
    if (ratio300 > 0.7 and misses == 0) or ratio300 > 0.8:
        return "B"
    if ratio300 > 0.6:
        return "C"
    return "D"


def _grade_from_accuracy(accuracy: float, thresholds: tuple[float, ...]) -> str:
    if accuracy == 100:
        return "X"
    for grade, threshold in zip("SABC", thresholds, strict=True):
        if accuracy > threshold:
            return grade
    return "D"


def stable_grade(
    play_mode: int,
    mods: int,
    count_300: int,
    count_100: int,
    count_50: int,
    count_katus: int,
    count_gekis: int,
    count_misses: int,
    completed: int,
) -> str:
    if completed == 0:
        return "F"

    if play_mode == 2:
        hits = count_300 + count_100 + count_50
        total = hits + count_katus + count_misses
        accuracy = hits / total * 100 if total else 0.0
        grade = _grade_from_accuracy(accuracy, (98, 94, 90, 85))
    elif play_mode == 3:
        total = (
            count_gekis + count_300 + count_katus + count_100 + count_50 + count_misses
        )
        points = (
            300 * (count_300 + count_gekis)
            + 200 * count_katus
            + 100 * count_100
            + 50 * count_50
        )
        accuracy = points / (300 * total) * 100 if total else 0.0
        grade = _grade_from_accuracy(accuracy, (95, 90, 80, 70))
    else:
        total = count_300 + count_100 + count_50 + count_misses
        grade = _grade_from_ratios(count_300, count_50, count_misses, total)

    if grade in ("X", "S") and mods & _SILVER_MODS:
        return grade + "H"
    return grade
