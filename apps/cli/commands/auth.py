"""
Auth command — JWT token generation for dashboard access.

Generates short-lived (default 5 min) or long-lived (24h for CI) JWTs
signed with HS256 using the MODELLENS_SECRET environment variable.

Usage:
    modellens auth token                   # 5-minute token
    modellens auth token --ttl 1440        # 24-hour token (CI)
    modellens auth token --ttl 0           # Non-expiring (not recommended)
"""

from __future__ import annotations

import os
import secrets
import sys
import time
from typing import Any, Dict

import click

# Ensure packages/ and apps/ are importable
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR))
_PACKAGES_DIR = os.path.join(_PROJECT_ROOT, "packages")
if _PACKAGES_DIR not in sys.path:
    sys.path.insert(0, _PACKAGES_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from core.jwt_utils import create_jwt, verify_jwt


# ── Secret management ──────────────────────────────────────────────


def _get_or_create_secret() -> str:
    """Get MODELLENS_SECRET from env, or generate and save one.

    The generated secret is persisted to ``~/.modellens/secret`` so
    that tokens issued before a restart remain valid.
    """
    secret = os.environ.get("MODELLENS_SECRET")
    if secret:
        return secret

    secret_path = os.path.expanduser("~/.modellens/secret")
    if os.path.exists(secret_path):
        with open(secret_path) as f:
            return f.read().strip()

    # Generate a new random secret
    os.makedirs(os.path.dirname(secret_path), exist_ok=True)
    new_secret = secrets.token_hex(32)
    with open(secret_path, "w") as f:
        f.write(new_secret)
    os.chmod(secret_path, 0o600)

    click.echo(
        "Generated new secret at ~/.modellens/secret.\n"
        "\n"
        "IMPORTANT: If deploying the dashboard to Cloudflare Pages,\n"
        f"  set this value as the MODELLENS_SECRET Cloudflare secret:\n"
        f"    npx wrangler secret put MODELLENS_SECRET\n"
        "\n"
        "If running locally, ensure the dashboard uses the same secret\n"
        "  (set MODELLENS_SECRET env var or use the same ~/.modellens/secret).\n",
        err=True,
    )

    return new_secret


# ── Click command ──────────────────────────────────────────────────


@click.group(name="auth")
def auth():
    """Authentication and token management for the dashboard."""
    pass


@auth.command(name="token")
@click.option(
    "--ttl", type=int, default=5,
    help="Token lifetime in minutes (0 = no expiry, default: 5).",
)
def token(ttl: int):
    """Generate a JWT for dashboard access.

    The token is signed with HS256 using the MODELLENS_SECRET env var
    (or an auto-generated secret at ~/.modellens/secret).

    Pass the token to the dashboard via:
      - Authorization: Bearer <token> header (API calls)
      - ?token=<token> query parameter (SSE EventSource connections)

    \\b
    Examples:
      modellens auth token                  # 5-minute token
      modellens auth token --ttl 60         # 1-hour token
      modellens auth token --ttl 0          # Non-expiring (CI)
    """
    secret = _get_or_create_secret()

    payload: Dict[str, Any] = {
        "sub": "modellens-cli",
        "iss": "modellens",
    }

    if ttl > 0:
        payload["exp"] = int(time.time()) + (ttl * 60)

    jwt = create_jwt(payload, secret)

    click.echo(jwt)

    if ttl > 0:
        click.echo(f"\nToken valid for {ttl} minute(s).", err=True)
    else:
        click.echo("\nToken has no expiry.", err=True)
    click.echo(
        f"Use with:  Authorization: Bearer {jwt[:20]}...",
        err=True,
    )
    click.echo(
        "Or for SSE:  EventSource(url + '?token=...')",
        err=True,
    )
