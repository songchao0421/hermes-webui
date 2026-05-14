"""
Hermes WebUI - Authentication Module
Token-based API authentication for securing endpoints.
Now supports both user tokens (from user_auth) and legacy server token.
"""

import os
import secrets
import logging
from pathlib import Path
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import get_auth_dir, get_auth_token_file
from user_auth import verify_token as verify_user_token

logger = logging.getLogger(__name__)

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
    """Get existing server token or generate a new one."""
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    return token


def verify_token(token: str) -> Optional[str]:
    """Verify a token. Returns 'server' for server token, username for user token, or None."""
    stored = get_or_create_token()
    if secrets.compare_digest(token, stored):
        return "server"
    # Also try user token
    username = verify_user_token(token)
    if username:
        return username
    return None


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
):
    """
    FastAPI dependency that enforces authentication.
    Skips the following paths:
    - /api/auth/* (login/register)
    - /health, /api/health
    - Static files and frontend
    - Avatar images (GET)
    """
    if not _auth_enabled:
        return

    # Allow auth endpoints (login/register)
    if request.url.path.startswith("/api/auth/"):
        return

    # Allow health check
    if request.url.path in ("/health", "/api/health"):
        return

    # Allow static files and frontend without auth
    if not request.url.path.startswith("/api/"):
        return

    # Allow avatar images
    if request.url.path.startswith("/api/persona/avatar/") and request.method == "GET":
        return

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = verify_token(credentials.credentials)
    if not result:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Store user info in request state
    request.state.auth_user = result