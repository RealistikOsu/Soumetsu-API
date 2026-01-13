from __future__ import annotations

from enum import IntFlag


class UserPrivileges(IntFlag):
    PUBLIC = 1 << 0
    NORMAL = 1 << 1
    DONOR = 1 << 2
    ADMIN_ACCESS_RAP = 1 << 3
    ADMIN_MANAGE_USERS = 1 << 4
    ADMIN_BAN_USERS = 1 << 5
    ADMIN_SILENCE_USERS = 1 << 6
    ADMIN_WIPE_USERS = 1 << 7
    ADMIN_MANAGE_BEATMAP = 1 << 8
    ADMIN_MANAGE_SERVER = 1 << 9
    ADMIN_MANAGE_SETTING = 1 << 10
    ADMIN_MANAGE_BETA_KEY = 1 << 11
    ADMIN_MANAGE_REPORT = 1 << 12
    ADMIN_MANAGE_DOCS = 1 << 13
    ADMIN_MANAGE_BADGES = 1 << 14
    ADMIN_VIEW_RAP_LOGS = 1 << 15
    ADMIN_MANAGE_PRIVILEGE = 1 << 16
    ADMIN_SEND_ALERTS = 1 << 17
    ADMIN_CHAT_MOD = 1 << 18
    ADMIN_KICK_USERS = 1 << 19
    PENDING_VERIFICATION = 1 << 20
    TOURNAMENT_STAFF = 1 << 21
    ADMIN_CAKER = 1 << 22


class TokenPrivileges(IntFlag):
    READ = 1 << 0
    READ_CONFIDENTIAL = 1 << 1
    WRITE = 1 << 2
    MANAGE_BADGES = 1 << 3
    BETA_KEYS = 1 << 4
    MANAGE_SETTINGS = 1 << 5
    VIEW_USER_ADVANCED = 1 << 6
    MANAGE_USER = 1 << 7
    MANAGE_ROLES = 1 << 8
    MANAGE_API_KEYS = 1 << 9
    BLOG = 1 << 10
    API_META = 1 << 11
    BEATMAP = 1 << 12
    BANCHO = 1 << 13


PRIVILEGE_REQUIREMENTS: dict[TokenPrivileges, UserPrivileges] = {
    TokenPrivileges.READ: UserPrivileges(1 << 30),
    TokenPrivileges.READ_CONFIDENTIAL: UserPrivileges.NORMAL,
    TokenPrivileges.WRITE: UserPrivileges.NORMAL,
    TokenPrivileges.MANAGE_BADGES: (
        UserPrivileges.ADMIN_ACCESS_RAP | UserPrivileges.ADMIN_MANAGE_BADGES
    ),
    TokenPrivileges.BETA_KEYS: (
        UserPrivileges.ADMIN_ACCESS_RAP | UserPrivileges.ADMIN_MANAGE_BETA_KEY
    ),
    TokenPrivileges.MANAGE_SETTINGS: (
        UserPrivileges.ADMIN_ACCESS_RAP | UserPrivileges.ADMIN_MANAGE_SETTING
    ),
    TokenPrivileges.VIEW_USER_ADVANCED: UserPrivileges.ADMIN_ACCESS_RAP,
    TokenPrivileges.MANAGE_USER: (
        UserPrivileges.ADMIN_ACCESS_RAP
        | UserPrivileges.ADMIN_MANAGE_USERS
        | UserPrivileges.ADMIN_BAN_USERS
    ),
    TokenPrivileges.MANAGE_ROLES: (
        UserPrivileges.ADMIN_ACCESS_RAP
        | UserPrivileges.ADMIN_MANAGE_USERS
        | UserPrivileges.ADMIN_MANAGE_PRIVILEGE
    ),
    TokenPrivileges.MANAGE_API_KEYS: (
        UserPrivileges.ADMIN_ACCESS_RAP
        | UserPrivileges.ADMIN_MANAGE_USERS
        | UserPrivileges.ADMIN_MANAGE_SERVER
    ),
    TokenPrivileges.BLOG: UserPrivileges.ADMIN_CHAT_MOD,
    TokenPrivileges.API_META: UserPrivileges.ADMIN_MANAGE_SERVER,
    TokenPrivileges.BEATMAP: (
        UserPrivileges.ADMIN_ACCESS_RAP | UserPrivileges.ADMIN_MANAGE_BEATMAP
    ),
    TokenPrivileges.BANCHO: UserPrivileges.NORMAL,
}


def filter_token_privileges(
    token_privileges: TokenPrivileges,
    user_privileges: UserPrivileges,
) -> TokenPrivileges:
    result = TokenPrivileges(0)
    for priv in TokenPrivileges:
        if token_privileges & priv:
            required = PRIVILEGE_REQUIREMENTS.get(priv, UserPrivileges(0))
            if user_privileges & required == required:
                result |= priv
    return result


def has_privilege(privileges: int, required: int) -> bool:
    return (privileges & required) == required


def is_restricted(user_privileges: UserPrivileges) -> bool:
    return not bool(user_privileges & UserPrivileges.NORMAL)


def is_pending_verification(user_privileges: UserPrivileges) -> bool:
    return bool(user_privileges & UserPrivileges.PENDING_VERIFICATION)


def is_donor(user_privileges: UserPrivileges) -> bool:
    return bool(user_privileges & UserPrivileges.DONOR)


def is_admin(user_privileges: UserPrivileges) -> bool:
    return bool(user_privileges & UserPrivileges.ADMIN_ACCESS_RAP)
