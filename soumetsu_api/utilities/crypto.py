from __future__ import annotations

import asyncio
import hashlib
import secrets

import bcrypt


def generate_token(length: int = 32) -> str:
    return secrets.token_hex(length // 2)


def hash_token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_token_md5(token: str) -> str:
    return hashlib.md5(token.encode()).hexdigest()


def _hash_password_sync(password: str) -> str:
    md5_hash = hashlib.md5(password.encode()).hexdigest()
    return bcrypt.hashpw(md5_hash.encode(), bcrypt.gensalt()).decode()


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hash_password_sync, password)


def _verify_password_sync(password: str, hashed: str) -> bool:
    try:
        md5_hash = hashlib.md5(password.encode()).hexdigest()
        return bcrypt.checkpw(md5_hash.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


async def verify_password(password: str, hashed: str) -> bool:
    return await asyncio.to_thread(_verify_password_sync, password, hashed)


def verify_password_md5(password: str, stored_hash: str) -> bool:
    return hashlib.md5(password.encode()).hexdigest() == stored_hash
