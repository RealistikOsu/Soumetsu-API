from __future__ import annotations

from enum import IntFlag


class UserPrivileges(IntFlag):
    # --- canonical v2 bits (docs/reference/privileges.md) ---
    ACTIVATED = 1 << 0             # 1
    DONOR = 1 << 1                 # 2
    ADMIN_MANAGE_USERS = 1 << 2    # 4  (ban/silence/restrict/wipe/kick/chat-mod folded here)
    ADMIN_VIEW_RAP_LOGS = 1 << 3   # 8
    ADMIN_MANAGE_REPORT = 1 << 4   # 16
    ADMIN_MANAGE_CLANS = 1 << 5    # 32
    ADMIN_SEND_ALERTS = 1 << 6     # 64
    ADMIN_MANAGE_SETTING = 1 << 7  # 128
    ADMIN_MANAGE_BADGES = 1 << 8   # 256
    ADMIN_MANAGE_PRIVILEGE = 1 << 9  # 512
    DEV_VIEW_ERROR_LOGS = 1 << 10  # 1024
    TOURNAMENT_STAFF = 1 << 11     # 2048
    BOT = 1 << 12                  # 4096
    BN_STD = 1 << 13               # 8192
    BN_TAIKO = 1 << 14             # 16384
    BN_CTB = 1 << 15               # 32768
    BN_MANIA = 1 << 16             # 65536

    # --- legacy aliases (old Ripple names -> v2 bits) so consumers keep working ---
    NORMAL = ACTIVATED
    ADMIN_ACCESS_RAP = ADMIN_VIEW_RAP_LOGS
    ADMIN_BAN_USERS = ADMIN_MANAGE_USERS
    ADMIN_SILENCE_USERS = ADMIN_MANAGE_USERS
    ADMIN_WIPE_USERS = ADMIN_MANAGE_USERS
    ADMIN_KICK_USERS = ADMIN_MANAGE_USERS
    ADMIN_CHAT_MOD = ADMIN_MANAGE_USERS
    ADMIN_MANAGE_SERVER = ADMIN_MANAGE_SETTING
    ADMIN_MANAGE_BETA_KEY = ADMIN_MANAGE_SETTING
    ADMIN_MANAGE_BEATMAP = BN_STD | BN_TAIKO | BN_CTB | BN_MANIA


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
    return not bool(user_privileges & UserPrivileges.ACTIVATED)


def is_pending_verification(user_privileges: UserPrivileges) -> bool:
    # v2 has no dedicated pending bit: a not-yet-activated account (ACTIVATED
    # unset) is pending activation.
    return not bool(user_privileges & UserPrivileges.ACTIVATED)


def is_donor(user_privileges: UserPrivileges) -> bool:
    return bool(user_privileges & UserPrivileges.DONOR)


def is_admin(user_privileges: UserPrivileges) -> bool:
    return bool(user_privileges & UserPrivileges.ADMIN_ACCESS_RAP)
