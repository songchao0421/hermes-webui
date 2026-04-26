"""
Hermes WebUI — Sessions Router
Conversation session management.
"""
from datetime import datetime

from fastapi import APIRouter

router = APIRouter(tags=["sessions"])

# Module-level globals (injected by app.py)
_conversations = None
_current_session_id = None
_SESSIONS_DIR = None
_load_session = None
_evict_old_sessions = None


@router.get("/api/sessions")
async def get_sessions():
    """List conversation sessions."""
    sessions = []
    for sid, msgs in _conversations.items():
        sessions.append({
            "id": sid,
            "name": msgs[0]["content"][:50] if msgs else "New Session",
            "message_count": len(msgs),
            "created": msgs[0].get("timestamp", "") if msgs else "",
        })

    for filepath in _SESSIONS_DIR.glob("*.json"):
        session_id = filepath.stem
        if session_id not in _conversations:
            messages = _load_session(session_id)
            if messages:
                sessions.append({
                    "id": session_id,
                    "name": messages[0]["content"][:50] if messages else "New Session",
                    "message_count": len(messages),
                    "created": messages[0].get("timestamp", "") if messages else "",
                })

    sessions.sort(key=lambda x: x["created"] or "", reverse=True)
    return {"sessions": sessions, "current": _current_session_id}


@router.post("/api/sessions/new")
async def new_session():
    """Create a new conversation session."""
    global _current_session_id
    _current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    _conversations[_current_session_id] = []
    _evict_old_sessions()
    return {"session_id": _current_session_id}


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session."""
    global _current_session_id
    if session_id in _conversations:
        del _conversations[session_id]
    filepath = _SESSIONS_DIR / f"{session_id}.json"
    if filepath.exists():
        filepath.unlink()
    if _current_session_id == session_id:
        _current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        _conversations[_current_session_id] = []
    return {"status": "ok"}


@router.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Get messages for a session."""
    if session_id in _conversations:
        return {"messages": _conversations[session_id]}
    messages = _load_session(session_id)
    _conversations[session_id] = messages
    return {"messages": messages}
