from __future__ import annotations

from enum import IntFlag
from typing import Any

from pydantic import BaseModel


class OsuMods(IntFlag):
    NF = 1 << 0
    EZ = 1 << 1
    TD = 1 << 2
    HD = 1 << 3
    HR = 1 << 4
    SD = 1 << 5
    DT = 1 << 6
    RX = 1 << 7
    HT = 1 << 8
    NC = 1 << 9
    FL = 1 << 10
    AT = 1 << 11
    SO = 1 << 12
    AP = 1 << 13
    PF = 1 << 14
    K4 = 1 << 15
    K5 = 1 << 16
    K6 = 1 << 17
    K7 = 1 << 18
    K8 = 1 << 19
    FI = 1 << 20
    RD = 1 << 21
    CN = 1 << 22
    TG = 1 << 23
    K9 = 1 << 24
    KC = 1 << 25
    K1 = 1 << 26
    K3 = 1 << 27
    K2 = 1 << 28
    V2 = 1 << 29
    MR = 1 << 30


MOD_ACRONYMS: tuple[str, ...] = (
    "NF",
    "EZ",
    "TD",
    "HD",
    "HR",
    "SD",
    "DT",
    "RX",
    "HT",
    "NC",
    "FL",
    "AT",
    "SO",
    "AP",
    "PF",
    "K4",
    "K5",
    "K6",
    "K7",
    "K8",
    "FI",
    "RD",
    "CN",
    "TG",
    "K9",
    "KC",
    "K1",
    "K3",
    "K2",
    "V2",
    "MR",
)


_SPEED_CHANGE_ACRONYMS = frozenset({"DT", "HT", "NC"})


class Mod(BaseModel):
    acronym: str
    settings: dict[str, Any] | None = None


def mods_from_score(mods: int, playback_rate: float) -> list[Mod]:
    result: list[Mod] = [Mod(acronym="CL")]

    # NC implies DT in the legacy bitmask; suppress DT so it doesn't
    # double-emit alongside NC.
    if mods & OsuMods.NC:
        mods &= ~int(OsuMods.DT)

    speed_change = round(playback_rate, 2)

    for i, acronym in enumerate(MOD_ACRONYMS):
        if not (mods & (1 << i)):
            continue

        settings: dict[str, Any] | None = None
        if acronym in _SPEED_CHANGE_ACRONYMS:
            settings = {
                "speed_change": speed_change,
                "adjust_pitch": acronym == "NC",
            }

        result.append(Mod(acronym=acronym, settings=settings))

    return result
