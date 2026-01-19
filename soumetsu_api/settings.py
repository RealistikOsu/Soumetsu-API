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

# hCaptcha (bot protection)
HCAPTCHA_SECRET_KEY = os.environ.get("SOUMETSUAPI_HCAPTCHA_SECRET_KEY", "")
HCAPTCHA_ENABLED = (
    os.environ.get("SOUMETSUAPI_HCAPTCHA_ENABLED", "true").lower() == "true"
)

# File storage
STORAGE_PATH = os.environ.get("SOUMETSUAPI_STORAGE_PATH", "/data")
AVATAR_PATH = os.path.join(STORAGE_PATH, "avatars")
BANNER_PATH = os.path.join(STORAGE_PATH, "banners")
MAX_AVATAR_SIZE = int(
    os.environ.get("SOUMETSUAPI_MAX_AVATAR_SIZE", 2 * 1024 * 1024),
)  # 2MB
MAX_BANNER_SIZE = int(
    os.environ.get("SOUMETSUAPI_MAX_BANNER_SIZE", 5 * 1024 * 1024),
)  # 5MB

# Rate limiting
RATE_LIMIT_ENABLED = (
    os.environ.get("SOUMETSUAPI_RATE_LIMIT_ENABLED", "true").lower() == "true"
)

# API versioning
API_VERSION = "v2"
