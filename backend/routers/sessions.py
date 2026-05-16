"""
Hermes WebUI — Sessions Router
Conversation session management.
v2.1: 多用户隔离 — 所有 API 按当前用户过滤，防止跨用户数据泄露。
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from services.session_manager import (
    get_sessions_for_user,
    get_owner_of_session,
    set_session_owner,
    remove_session_owner,
)
from audit import (
    audit_session_create,
    audit_session_delete,
    audit_conversation_access,
)

router = APIRouter(tags=["sessions"])

# Module-level globals (injected by app.py)
_conversations = None
_current_session_id = None
_SESSIONS_DIR = None
_load_session = None
_evict_old_sessions = None


def _get_user_id(request: Request) -> str:
    """从 request state 中获取当前用户 ID。"""
    username = getattr(request.state, "auth_user", None)
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")
    return username


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("/api/sessions")
async def get_sessions(request: Request):
    """List conversation sessions for current user."""
    user_id = _get_user_id(request)
    user_sessions = get_sessions_for_user(user_id)

    sessions = []
    for sid, msgs in user_sessions.items():
        sessions.append({
            "id": sid,
            "name": msgs[0]["content"][:50] if msgs else "New Session",
            "message_count": len(msgs),
            "created": msgs[0].get("timestamp", "") if msgs else "",
        })

    # 也加载磁盘中属于当前用户的 session
    for filepath in _SESSIONS_DIR.glob("*.json"):
        session_id = filepath.stem
        if session_id not in user_sessions:
            messages = _load_session(session_id)
            owner = get_owner_of_session(session_id)
            if messages and (owner == user_id or owner is None):
                # owner 为 None 的是旧数据，归当前用户
                if owner is None:
                    set_session_owner(session_id, user_id)
                sessions.append({
                    "id": session_id,
                    "name": messages[0]["content"][:50] if messages else "New Session",
                    "message_count": len(messages),
                    "created": messages[0].get("timestamp", "") if messages else "",
                })

    sessions.sort(key=lambda x: x["created"] or "", reverse=True)
    return {"sessions": sessions, "current": _current_session_id}


@router.post("/api/sessions/new")
async def new_session(request: Request):
    """Create a new conversation session for the current user."""
    global _current_session_id
    user_id = _get_user_id(request)

    _current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    _conversations[user_id][_current_session_id] = []
    set_session_owner(_current_session_id, user_id)
    _evict_old_sessions()

    audit_session_create(user_id, _current_session_id, _get_client_ip(request))
    return {"session_id": _current_session_id}


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    """Delete a conversation session (only own sessions)."""
    global _current_session_id
    user_id = _get_user_id(request)

    owner = get_owner_of_session(session_id)
    if owner and owner != user_id:
        raise HTTPException(status_code=403, detail="无权删除他人会话")

    # 从内存中删除
    if user_id in _conversations and session_id in _conversations[user_id]:
        del _conversations[user_id][session_id]

    # 从磁盘删除
    for ext in (".enc", ".json"):
        filepath = _SESSIONS_DIR / f"{session_id}{ext}"
        if filepath.exists():
            filepath.unlink()

    remove_session_owner(session_id)

    if _current_session_id == session_id:
        _current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        _conversations[user_id][_current_session_id] = []
        set_session_owner(_current_session_id, user_id)

    audit_session_delete(user_id, session_id, _get_client_ip(request))
    return {"status": "ok"}


@router.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, request: Request):
    """Get messages for a session (only own sessions)."""
    user_id = _get_user_id(request)

    # 检查 session 归属
    owner = get_owner_of_session(session_id)
    if owner and owner != user_id:
        raise HTTPException(status_code=403, detail="无权查看他人会话")

    if user_id in _conversations and session_id in _conversations[user_id]:
        audit_conversation_access(user_id, session_id, _get_client_ip(request))
        return {"messages": _conversations[user_id][session_id]}

    messages = _load_session(session_id)
    if messages:
        _conversations[user_id][session_id] = messages
        set_session_owner(session_id, user_id)

    audit_conversation_access(user_id, session_id, _get_client_ip(request))
    return {"messages": messages}
