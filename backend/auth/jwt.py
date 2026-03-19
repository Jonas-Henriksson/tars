"""JWT token creation and verification."""
from __future__ import annotations

import hashlib
import hmac
import json
import base64
import time
import os
from typing import Any

# Secret key — loaded from env or generated on first run
_SECRET_KEY = os.environ.get("TARS_JWT_SECRET", "")
if not _SECRET_KEY:
    _secret_file = os.path.join(os.path.dirname(__file__), "..", "..", ".jwt_secret")
    if os.path.exists(_secret_file):
        with open(_secret_file) as f:
            _SECRET_KEY = f.read().strip()
    else:
        _SECRET_KEY = os.urandom(32).hex()
        os.makedirs(os.path.dirname(_secret_file), exist_ok=True)
        with open(_secret_file, "w") as f:
            f.write(_SECRET_KEY)

TOKEN_EXPIRY_SECONDS = 86400 * 7  # 7 days


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_token(payload: dict[str, Any]) -> str:
    """Create a JWT token with the given payload."""
    header = {"alg": "HS256", "typ": "JWT"}

    payload = {
        **payload,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS,
    }

    header_b64 = _b64url_encode(json.dumps(header).encode())
    payload_b64 = _b64url_encode(json.dumps(payload).encode())

    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        _SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token and return the payload, or None if invalid."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            _SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256
        ).digest()

        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode payload
        payload = json.loads(_b64url_decode(payload_b64))

        # Check expiration
        if payload.get("exp", 0) < time.time():
            return None

        return payload

    except Exception:
        return None


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{salt.hex()}:{key.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    try:
        salt_hex, key_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(key_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return hmac.compare_digest(expected, actual)
    except Exception:
        return False
