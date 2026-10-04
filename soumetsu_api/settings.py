from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

APP_COMPONENT = os.environ["APP_COMPONENT"]

# MySQL configuration
MYSQL_HOST = os.environ["MYSQL_HOST"]
MYSQL_TCP_PORT = int(os.environ["MYSQL_TCP_PORT"])
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
MYSQL_DATABASE = os.environ["MYSQL_DATABASE"]

# Redis configuration
REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
REDIS_DATABASE = int(os.environ["REDIS_DATABASE"])

# CORS configuration (comma-separated list of origins, empty to disable)
CORS_ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.environ.get("SOUMETSUAPI_CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

# Session configuration
SESSION_TTL_SECONDS = int(
    os.environ.get("SOUMETSUAPI_SESSION_TTL_SECONDS", 60 * 60 * 24 * 30),
)  # 30 days
SESSION_SLIDING_WINDOW = (
    os.environ.get("SOUMETSUAPI_SESSION_SLIDING_WINDOW", "true").lower() == "true"
)

# Discord OAuth (account linking)
DISCORD_APP_CLIENT_ID = os.environ.get("DISCORD_APP_CLIENT_ID", "")
DISCORD_APP_CLIENT_SECRET = os.environ.get("DISCORD_APP_CLIENT_SECRET", "")
DISCORD_USER_LOOKUP_URL = os.environ.get(
    "DISCORD_USER_LOOKUP_URL",
    "https://discordlookup.mesalytic.moe/v1/user",
).rstrip("/")

# Rank requests: how many can be open across the server, and per player, over the last 24 hours.
RANK_QUEUE_SIZE = int(os.environ.get("SOUMETSUAPI_RANK_QUEUE_SIZE", 500))
RANK_REQUESTS_PER_USER = int(os.environ.get("SOUMETSUAPI_RANK_REQUESTS_PER_USER", 25))

# hCaptcha (bot protection)
HCAPTCHA_SECRET_KEY = os.environ.get("SOUMETSUAPI_HCAPTCHA_SECRET_KEY", "")
HCAPTCHA_ENABLED = (
    os.environ.get("SOUMETSUAPI_HCAPTCHA_ENABLED", "true").lower() == "true"
)

# File storage
STORAGE_PATH = os.environ.get("SOUMETSUAPI_STORAGE_PATH", "/data")
AVATAR_PATH = os.path.join(STORAGE_PATH, "avatars")
BANNER_PATH = os.path.join(STORAGE_PATH, "banners")
CLAN_ICON_PATH = os.path.join(STORAGE_PATH, "clan-icons")
MAX_AVATAR_SIZE = int(
    os.environ.get("SOUMETSUAPI_MAX_AVATAR_SIZE", 2 * 1024 * 1024),
)  # 2MB
MAX_BANNER_SIZE = int(
    os.environ.get("SOUMETSUAPI_MAX_BANNER_SIZE", 5 * 1024 * 1024),
)  # 5MB
MAX_CLAN_ICON_SIZE = int(
    os.environ.get("SOUMETSUAPI_MAX_CLAN_ICON_SIZE", 2 * 1024 * 1024),
)  # 2MB

# API versioning
API_VERSION = "v2"

# Two-factor: secrets are encrypted with this key (32 bytes, base64). Staff setup is confirmed by email.
TOTP_ENCRYPTION_KEY = os.environ.get("SOUMETSUAPI_TOTP_ENCRYPTION_KEY", "")
BREVO_API_KEY = os.environ.get("SOUMETSUAPI_BREVO_API_KEY", "")
# Same format as Soumetsu's BREVO_FROM: "RealistikOsu" <no-reply@ussr.pl>
MAIL_FROM = os.environ.get("SOUMETSUAPI_MAIL_FROM", "")
APP_BASE_URL = os.environ.get("SOUMETSUAPI_APP_BASE_URL", "https://ussr.pl").rstrip("/")
