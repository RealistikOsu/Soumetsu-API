from __future__ import annotations

import hashlib
import secrets

import bcrypt


def generate_token(length: int = 32) -> str:
    return secrets.token_hex(length // 2)


def hash_token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_token_md5(token: str) -> str:
    return hashlib.md5(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def verify_password_md5(password: str, stored_hash: str) -> bool:
    return hashlib.md5(password.encode()).hexdigest() == stored_hash
