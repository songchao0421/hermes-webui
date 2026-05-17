"""
Hermes WebUI — 管理员路由
==========================
只有 server token（管理员）可访问的 API。

端点:
  GET  /api/admin/users           — 列出所有用户
  POST /api/admin/users/disable   — 停用用户
  POST /api/admin/users/enable    — 启用用户
  POST /api/admin/users/reset-password — 重置密码
  GET  /api/admin/audit           — 查看最近的审计日志
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from user_auth import (
    list_users,
    set_user_enabled,
    admin_reset_password,
)
from audit import AUDIT_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Pydantic Models ──────────────────────────────────────────────────

class UserActionRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)


class ResetPasswordRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    new_password: str = Field(..., min_length=8, max_length=128)


# ── 权限检查 ─────────────────────────────────────────────────────────

def _require_admin(request: Request):
    """检查当前请求是否来自管理员（server token）。"""
    username = getattr(request.state, "auth_user", None)
    if username != "server":
        raise HTTPException(status_code=403, detail="仅限管理员访问")
    return username


# ── Routes ───────────────────────────────────────────────────────────

@router.get("/users")
async def api_list_users(request: Request):
    """列出所有用户及状态。"""
    _require_admin(request)
    return {"users": list_users(), "total": len(list_users())}


@router.post("/users/disable")
async def api_disable_user(req: UserActionRequest, request: Request):
    """停用指定用户账号。"""
    admin = _require_admin(request)
    if req.username == "server":
        raise HTTPException(status_code=400, detail="不能停用管理员账号")
    result = set_user_enabled(req.username.strip(), enabled=False)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    from audit import audit_user_disable
    audit_user_disable(admin, req.username.strip(), _get_ip(request))
    return result


@router.post("/users/enable")
async def api_enable_user(req: UserActionRequest, request: Request):
    """启用指定用户账号。"""
    admin = _require_admin(request)
    result = set_user_enabled(req.username.strip(), enabled=True)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    from audit import audit_user_enable
    audit_user_enable(admin, req.username.strip(), _get_ip(request))
    return result


@router.post("/users/reset-password")
async def api_reset_password(req: ResetPasswordRequest, request: Request):
    """管理员重置用户密码。"""
    admin = _require_admin(request)
    result = admin_reset_password(req.username.strip(), req.new_password)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    from audit import audit_password_reset
    audit_password_reset(admin, req.username.strip(), _get_ip(request))
    return result


@router.get("/audit")
async def api_get_audit_logs(request: Request, limit: int = 100):
    """查看最近的审计日志（最近 N 条）。"""
    _require_admin(request)

    entries = []
    if AUDIT_DIR.exists():
        # 按日期排序取最近的日志文件
        log_files = sorted(AUDIT_DIR.glob("audit_*.jsonl"), reverse=True)
        import json
        for lf in log_files:
            try:
                lines = lf.read_text(encoding="utf-8").strip().splitlines()
                # 从最近的开始加
                for line in reversed(lines):
                    if not line.strip():
                        continue
                    entries.append(json.loads(line))
                    if len(entries) >= limit:
                        break
            except Exception:
                continue
            if len(entries) >= limit:
                break

    return {"entries": entries[:limit], "total": len(entries[:limit])}


# ── Helpers ──────────────────────────────────────────────────────────

def _get_ip(request: Request) -> str:
    """提取客户端 IP，X-Forwarded-For 仅当直连 IP 属于可信代理时才使用。"""
    from config import resolve_client_ip
    return resolve_client_ip(request)
