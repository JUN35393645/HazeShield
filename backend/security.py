from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time


_PASSWORD_ITERATIONS = 310_000
_SESSION_TTL_SECONDS = 60 * 60 * 12
_configured_secret = os.environ.get("HAZESHIELD_SESSION_SECRET")
_SESSION_SECRET = _configured_secret.encode() if _configured_secret else secrets.token_bytes(32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${_PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


def issue_session_token(user_id: int) -> str:
    expires = int(time.time()) + _SESSION_TTL_SECONDS
    payload = f"{user_id}:{expires}".encode()
    signature = hmac.new(_SESSION_SECRET, payload, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signed = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{token}.{signed}"


def session_user_id(token: str) -> int | None:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        expected = hmac.new(_SESSION_SECRET, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        user_id_text, expires_text = payload.decode().split(":", 1)
        if int(expires_text) < int(time.time()):
            return None
        return int(user_id_text)
    except (ValueError, UnicodeDecodeError):
        return None
