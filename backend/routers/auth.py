"""Hermes WebUI — User Auth Router (Login/Register API)
v2.2: 密码过期检查 + 修改密码 + Token TTL 活动续期。
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from user_auth import (
    register_user, login_user, logout_user, verify_token, get_user_workspace,
    change_password, check_token_expired, renew_token_activity,
)
from ratelimit import RateLimit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str
    password: str


class TokenRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


def _get_client_ip(request: Request) -> str:
    """提取客户端 IP，X-Forwarded-For 仅当直连 IP 属于可信代理时才使用。"""
    from config import resolve_client_ip
    return resolve_client_ip(request)


@router.post("/register")
async def api_register(req: AuthRequest, request: Request, _rate: None = Depends(RateLimit("10/hour"))):
    """Register a new user account."""
    result = register_user(req.username.strip(), req.password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    from audit import audit_register
    audit_register(req.username.strip(), _get_client_ip(request))
    return result


@router.post("/login")
async def api_login(req: AuthRequest, request: Request, _rate: None = Depends(RateLimit("10/minute"))):
    """Login with username and password."""
    result = login_user(req.username.strip(), req.password)
    if not result["success"]:
        # 判断是锁定还是密码错误
        if "锁定" in result.get("message", ""):
            from audit import audit_login_locked
            audit_login_locked(req.username.strip(), _get_client_ip(request))
        else:
            from audit import audit_login_failure
            audit_login_failure(req.username.strip(), result.get("message", ""), _get_client_ip(request))
        raise HTTPException(status_code=401, detail=result["message"])

    from audit import audit_login_success
    audit_login_success(req.username.strip(), _get_client_ip(request))
    return result


@router.post("/verify")
async def api_verify(req: TokenRequest, _rate: None = Depends(RateLimit("60/minute"))):
    """Verify a token and return user info. Also checks TTL."""
    username = verify_token(req.token)
    if not username:
        raise HTTPException(status_code=401, detail="Token 无效")

    # 检查 TTL
    if check_token_expired(req.token):
        raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")

    # 续期活动时间
    renew_token_activity(req.token)

    workspace = get_user_workspace(username)
    return {
        "success": True,
        "username": username,
        "workspace": str(workspace) if workspace else "",
    }


@router.post("/change-password")
async def api_change_password(req: ChangePasswordRequest, request: Request, _rate: None = Depends(RateLimit("5/minute"))):
    """用户自行修改密码。"""
    username = getattr(request.state, "auth_user", None)
    if not username or username == "server":
        raise HTTPException(status_code=401, detail="请先以用户身份登录")

    result = change_password(username, req.old_password, req.new_password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/logout")
async def api_logout(request: Request, _rate: None = Depends(RateLimit("20/minute"))):
    """服务端登出：清除当前 token，强制该设备下线。

    要求已登录。登出后客户端应清除 localStorage 中的 token。
    """
    username = getattr(request.state, "auth_user", None)
    if not username or username == "server":
        raise HTTPException(status_code=401, detail="请先以用户身份登录")

    result = logout_user(username)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result
