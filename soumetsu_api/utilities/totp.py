from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from soumetsu_api import settings

STEP_SECONDS = 30
DIGITS = 6
ISSUER = "RealistikOsu"


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def provisioning_uri(secret: str, username: str) -> str:
    label = quote(f"{ISSUER}:{username}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}"


def _code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


# The step the code belongs to, allowing one step of clock drift either way, or None when it's wrong. The
# caller records the step so the same code can't be used twice.
def matching_step(secret: str, code: str) -> int | None:
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    now = int(time.time()) // STEP_SECONDS
    for step in (now - 1, now, now + 1):
        if hmac.compare_digest(_code_at(secret, step), code):
            return step
    return None


# Secrets are stored encrypted, so a database dump alone isn't enough to generate codes.
def _key() -> bytes:
    if not settings.TOTP_ENCRYPTION_KEY:
        raise RuntimeError("SOUMETSUAPI_TOTP_ENCRYPTION_KEY is not set")
    return base64.b64decode(settings.TOTP_ENCRYPTION_KEY)


def encrypt(secret: str) -> str:
    nonce = os.urandom(12)
    blob = nonce + AESGCM(_key()).encrypt(nonce, secret.encode(), None)
    return base64.b64encode(blob).decode()


def decrypt(stored: str) -> str:
    blob = base64.b64decode(stored)
    return AESGCM(_key()).decrypt(blob[:12], blob[12:], None).decode()


def new_recovery_codes(count: int = 8) -> list[str]:
    return [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().lower().encode()).hexdigest()
