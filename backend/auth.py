"""backend/auth.py — password hashing + JWT helpers (Session 6).

Extracted verbatim from ``main.py``. Reads its secret / algorithm / token
lifetime from ``config.settings`` (previously module-level constants driven by
``os.getenv("JWT_SECRET")``).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import jwt

from config import settings

SECRET_KEY = settings.jwt_secret
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_HOURS = settings.access_token_expire_hours


def _hash_pw(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${h.hex()}"


def _verify_pw(password: str, stored: str) -> bool:
    salt, hx = stored.split("$", 1)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return h.hex() == hx


def create_token(user_id: str, role: str = "patient") -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": user_id, "role": role, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(401, "Invalid token")
