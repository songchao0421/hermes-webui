"""Hermes WebUI — User Auth Router (Login/Register API)"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from user_auth import register_user, login_user, verify_token, get_user_workspace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str
    password: str


class TokenRequest(BaseModel):
    token: str


@router.post("/register")
async def api_register(req: AuthRequest):
    """Register a new user account."""
    result = register_user(req.username.strip(), req.password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/login")
async def api_login(req: AuthRequest):
    """Login with username and password."""
    result = login_user(req.username.strip(), req.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["message"])
    return result


@router.post("/verify")
async def api_verify(req: TokenRequest):
    """Verify a token and return user info."""
    username = verify_token(req.token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    workspace = get_user_workspace(username)
    return {
        "success": True,
        "username": username,
        "workspace": str(workspace) if workspace else "",
    }
