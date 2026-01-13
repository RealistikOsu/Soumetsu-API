from __future__ import annotations

import re

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9 _\[\]-]{2,15}$")
CLAN_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 '_\[\]-]{2,15}$")
CLAN_TAG_PATTERN = re.compile(r"^[A-Za-z0-9]{2,6}$")
HEX_COLOUR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")

COMMON_PASSWORDS = frozenset(
    {
        "password",
        "12345678",
        "123456789",
        "1234567890",
        "qwertyuiop",
        "iloveyou",
        "trustno1",
        "baseball",
        "football",
        "starwars",
        "superman",
        "1qaz2wsx",
        "jennifer",
        "sunshine",
        "computer",
        "michelle",
        "11111111",
        "princess",
        "987654321",
        "corvette",
        "1234qwer",
        "88888888",
        "internet",
        "samantha",
        "whatever",
        "maverick",
        "steelers",
        "mercedes",
        "123123123",
        "qwer1234",
        "hardcore",
        "q1w2e3r4",
        "midnight",
        "bigdaddy",
        "victoria",
        "1q2w3e4r",
        "cocacola",
        "marlboro",
        "asdfasdf",
        "87654321",
        "password1",
        "password123",
        "abc12345",
        "abcd1234",
        "qwerty123",
        "letmein1",
        "welcome1",
        "monkey123",
        "dragon123",
        "master123",
    },
)

FORBIDDEN_USERNAMES = frozenset(
    {
        "whitecat",
        "merami",
        "ppy",
        "peppy",
        "varvallian",
        "spare",
        "beasttroll",
        "beasttrollmc",
        "wubwubwolf",
        "whitew0lf",
        "vaxei",
        "alumetri",
        "mathi",
        "flyingtuna",
        "idke",
        "fgsky",
        "dxrkify",
        "karthy",
        "osu!",
        "freddie benson",
        "micca",
        "ryuk",
        "azr8",
        "toy",
        "fieryrage",
        "firebat92",
        "umbre",
        "mouseeasy",
        "bartek22830",
        "gashi",
        "moeyandere",
        "piggey",
        "angelism",
        "cookiezi",
        "nathan on osu",
        "chocomint",
        "wakson",
        "karuna",
        "monko2k",
        "koifishu",
        "bananya",
        "hvick",
        "hvick225",
        "sotarks",
        "rrtyui",
        "armin",
        "a r m i n",
        "rustbell",
        "thelewa",
        "happystick",
        "cptnxn",
        "reimu-desu",
        "bahamete",
        "azer",
        "axarious",
        "oxycodone",
        "sayonara-bye",
        "sapphireghost",
        "adamqs",
        "_index",
        "-gn",
        "rafis",
    },
)


class ValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValidationError(
            "Your password is too short! It must be at least 8 characters long.",
        )

    if password.lower() in COMMON_PASSWORDS:
        raise ValidationError(
            "Your password is one of the most common passwords on the entire internet. "
            "No way we're letting you use that!",
        )


def validate_username(username: str) -> None:
    if not USERNAME_PATTERN.match(username):
        raise ValidationError(
            "Your username must contain alphanumerical characters, spaces, or any of _[]-",
        )

    if "_" in username and " " in username:
        raise ValidationError("A username can't contain both underscores and spaces.")

    if username.lower() in FORBIDDEN_USERNAMES:
        raise ValidationError("You're not allowed to register with that username.")


def validate_clan_name(name: str) -> None:
    if not CLAN_NAME_PATTERN.match(name):
        raise ValidationError(
            "Clan name must be 2-15 characters and contain only "
            "alphanumerical characters, spaces, or '_[]-",
        )


def validate_clan_tag(tag: str) -> None:
    if not CLAN_TAG_PATTERN.match(tag):
        raise ValidationError("Clan tag must be 2-6 alphanumerical characters.")


def validate_hex_colour(colour: str) -> None:
    if not HEX_COLOUR_PATTERN.match(colour):
        raise ValidationError("Invalid colour format. Use hex format like #FF0000.")


def safe_username(username: str) -> str:
    return username.lower().replace(" ", "_")
