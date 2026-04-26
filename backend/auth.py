"""
Hermes WebUI - Authentication Module
Token-based API authentication for securing endpoints.
"""

import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import get_auth_dir, get_auth_token_file

AUTH_DIR = get_auth_dir()
TOKEN_FILE = get_auth_token_file()

# Module-level state
_auth_enabled = True
_security = HTTPBearer(auto_error=False)


def set_auth_enabled(enabled: bool):
    """Enable or disable authentication globally."""
    global _auth_enabled
    _auth_enabled = enabled


def is_auth_enabled() -> bool:
    return _auth_enabled


def get_or_create_token() -> str:
    """Get existing token or generate a new one."""
    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token

    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    # Restrict file permissions (owner-only read/write)
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass  # Windows doesn't support Unix permissions
    return token


def verify_token(token: str) -> bool:
    """Check if the provided token matches the stored token."""
    stored = get_or_create_token()
    return secrets.compare_digest(token, stored)


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
):
    """
    FastAPI dependency that enforces token authentication.
    Skipped when auth is disabled via --no-auth.
    """
    if not _auth_enabled:
        return

    # Allow health check without auth
    if request.url.path in ("/health", "/api/health"):
        return

    # Allow static files and frontend without auth
    if not request.url.path.startswith("/api/"):
        return

    # Allow avatar image access without auth (browser <img> tags don't send Bearer token)
    if request.url.path.startswith("/api/persona/avatar/") and request.method == "GET":
        return

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide token via Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_token(credentials.credentials):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
