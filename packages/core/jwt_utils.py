"""
Shared JWT utilities for Model Lens dashboard authentication.

Provides HS256 token creation and verification using only the Python standard
library (no PyJWT dependency).  Both ``apps/cli/commands/auth.py`` and
``packages/events/sse.py`` import from here instead of duplicating logic.

Usage:
    from core.jwt_utils import create_jwt, verify_jwt

    secret = "my-hmac-secret"
    token = create_jwt({"sub": "modellens-cli", "exp": 1234567890}, secret)
    payload = verify_jwt(token, secret)  # returns dict or None
"""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional


def b64url_encode(data: bytes) -> str:
    """Base64url-encode bytes (no padding)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(s: str) -> bytes:
    """Base64url-decode a string (adds padding if needed)."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_jwt(payload: Dict[str, Any], secret: str) -> str:
    """Create a signed JWT using HS256.

    Args:
        payload: The JWT claims (``iat`` is added if missing).
        secret: HMAC signing secret.

    Returns:
        A compact JWT string: ``header.payload.signature``.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    payload.setdefault("iat", int(time.time()))

    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode())

    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = b64url_encode(signature)

    return f"{signing_input}.{sig_b64}"


def verify_jwt(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """Verify a JWT signature and return the decoded payload.

    Returns ``None`` if the token is invalid or expired.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        actual_sig = b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode payload
        payload_bytes = b64url_decode(payload_b64)
        payload = json.loads(payload_bytes)

        # Check expiration
        exp = payload.get("exp")
        if exp is not None and time.time() > exp:
            return None  # Expired

        return payload
    except Exception:
        return None


def get_secret() -> Optional[str]:
    """Get MODELLENS_SECRET from environment.

    Returns ``None`` if the secret is not set or is using the default
    development value.
    """
    secret = os.environ.get("MODELLENS_SECRET")
    if not secret or secret == "modellens-dev-secret-change-me":
        return None
    return secret


__all__ = [
    "b64url_encode",
    "b64url_decode",
    "create_jwt",
    "verify_jwt",
    "get_secret",
]
