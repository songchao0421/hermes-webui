"""
Hermes WebUI — Agent Router (SDK Direct)
==========================================
Replaces the old subprocess-based agent execution with direct Hermes Agent
SDK calls via _hermes_sdk_bridge.py.

Endpoints:
  POST /api/agent/stream — start a streaming conversation turn (SSE)
  POST /api/agent/abort  — abort the running turn
"""
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

from models import AgentRequest
from config import get_upload_dir
from ratelimit import RateLimit
from _hermes_sdk_bridge import HermesSDKBridge
from services.session_manager import (
    get_owner_of_session,
    set_session_owner,
    get_session_lock,
)

logger = logging.getLogger("hermes_webui.agent")

router = APIRouter(prefix="/api/agent", tags=["agent"])

# ── Bridge singleton ─────────────────────────────────────────────────
_bridge: HermesSDKBridge = HermesSDKBridge()

# Session-level globals set by lifespan (app.py)
# conversations is now: dict[user_id][session_id] -> [messages]
_conversations = None
_current_session_id = None  # str
_save_session = None    # save_session(session_id, messages, owner=user_id)
_WSL_MODE = False
_model_switch = None    # model_switch module (for task routing)


def _get_user_id(request: Request) -> str:
    username = getattr(request.state, "auth_user", "anonymous")
    return username or "anonymous"


from ratelimit import _limit_agent_stream

@router.post("/stream")
async def agent_stream(payload: AgentRequest, request: Request, _rate: None = Depends(_limit_agent_stream)):
    """Start a conversation turn against the Hermes Agent SDK.

    Request body (JSON):
      {
        "message": "...",          // required
        "system_message": "...",   // optional
        "history": [...],          // optional — messages from current session
        "session_id": "...",       // optional
        "file_ids": [...]          // optional — list of uploaded file IDs
      }

    Returns: SSE stream of events as ``text/event-stream``.
    """
    user_message = payload.message.strip()
    system_message = payload.system_message
    history = payload.history or []
    session_id = payload.session_id
    file_ids = payload.file_ids or []

    # ── Resolve file_ids to absolute paths ──
    uploaded_paths = []
    if file_ids:
        upload_dir = get_upload_dir()
        for fid in file_ids:
            fp = upload_dir / fid
            if fp.exists():
                uploaded_paths.append(str(fp.resolve()))
            else:
                logger.warning("Uploaded file not found: %s", fid)

    # ── Task Routing Decision ──
    routing_info = {}
    try:
        from services.task_router import decide_routing
        active = _model_switch.get_active_profile() if _model_switch else None
        profiles_data = _model_switch.load_profiles() if _model_switch else {}
        decision = decide_routing(
            message=user_message,
            msg_dict=payload.model_dump(),
            active_profile=active,
            profiles=profiles_data,
        )
        routing_info = {
            "target_tier": decision["target_tier"],
            "score": decision["score"],
            "reason": decision["reason"],
            "needs_switch": decision["needs_switch"],
        }

        # Auto-switch if needed
        if decision["needs_switch"] and decision["target_profile_id"] and _model_switch:
            logger.info(
                "TaskRouter: auto-switching to %s (score=%d, reason=%s)",
                decision["target_profile_id"], decision["score"], decision["reason"],
            )
            result = _model_switch.switch_model(decision["target_profile_id"])
            if result.get("success"):
                routing_info["switched_to"] = decision["target_profile_id"]
            else:
                logger.warning("TaskRouter: auto-switch failed: %s", result.get("error"))
    except Exception as e:
        logger.warning("TaskRouter decision failed (non-fatal): %s", e)
        routing_info = {"error": str(e)}

    # ── Build conversation_history from session ──
    # Hermes SDK expects a list of {"role": "...", "content": "..."}
    conversation_history = []
    if history:
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                conversation_history.append({"role": role, "content": content})

    # ── SSE response ──
    from fastapi.responses import StreamingResponse

    async def event_stream():
        event_id = 0
        try:
            # Send routing decision as first event
            if routing_info:
                event_id += 1
                yield f"id: {event_id}\ndata: {json.dumps({'type': 'routing', **routing_info}, ensure_ascii=False)}\n\n"

            async for event in _bridge.run_conversation(
                user_message=user_message,
                system_message=system_message,
                conversation_history=conversation_history,
                session_id=session_id,
                file_paths=uploaded_paths or None,
            ):
                event_id += 1
                data = json.dumps(event, ensure_ascii=False)
                yield f"id: {event_id}\ndata: {data}\n\n"
        except Exception as exc:
            logger.exception("SSE stream error")
            data = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
            yield f"id: {event_id}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/abort")
async def agent_abort():
    """Abort the currently running conversation turn."""
    _bridge.abort()
    return {"ok": True, "message": "Abort signal sent"}


# ── 上传限制 ─────────────────────────────────────────────────────────
MAX_UPLOAD_SIZE = 200 * 1024 * 1024  # 200 MB


# ---------------------------------------------------------------------------
# Upload attachments
# ---------------------------------------------------------------------------

@router.post("/upload")
async def agent_upload(file: UploadFile = File(...), request: Request = None, _rate: None = Depends(RateLimit("10/minute"))):
    """Upload a file to be used as an attachment in the next agent message.

    Returns a file_id that can be passed to /api/agent/stream.
    Max file size: 200 MB.
    """
    upload_dir = get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "file").suffix
    file_id = str(uuid.uuid4()) + ext
    dest = upload_dir / file_id

    try:
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"文件过大，最大允许 {MAX_UPLOAD_SIZE // (1024*1024)} MB")
        dest.write_bytes(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    # 审计日志
    user_id = _get_user_id(request) if request else "unknown"
    from config import resolve_client_ip
    ip = resolve_client_ip(request) if request else "unknown"
    from audit import audit_file_upload
    audit_file_upload(user_id, file.filename or "file", len(content), ip)

    return {
        "file_id": file_id,
        "filename": file.filename or "file",
        "size": len(content),
        "path": str(dest),
    }


@router.post("/attachments")
async def agent_attachments(files: list[UploadFile] = File(...), request: Request = None, _rate: None = Depends(RateLimit("5/minute"))):
    """Upload multiple files at once. Returns list of file_id entries.
    Max per-file size: 200 MB.
    """
    upload_dir = get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)

    user_id = _get_user_id(request) if request else "unknown"
    from config import resolve_client_ip
    ip = resolve_client_ip(request) if request else "unknown"

    results = []
    for f in files:
        ext = Path(f.filename or "file").suffix
        file_id = str(uuid.uuid4()) + ext
        dest = upload_dir / file_id
        try:
            content = await f.read()
            if len(content) > MAX_UPLOAD_SIZE:
                results.append({
                    "file_id": None,
                    "filename": f.filename or "file",
                    "error": f"文件过大，最大允许 {MAX_UPLOAD_SIZE // (1024*1024)} MB",
                })
                continue
            dest.write_bytes(content)
            results.append({
                "file_id": file_id,
                "filename": f.filename or "file",
                "size": len(content),
                "path": str(dest),
            })
            from audit import audit_file_upload
            audit_file_upload(user_id, f.filename or "file", len(content), ip)
        except Exception as e:
            results.append({
                "file_id": None,
                "filename": f.filename or "file",
                "error": str(e),
            })
    return {"files": results}


# ---------------------------------------------------------------------------
# Session operations (undo / retry / rename) — user-isolated
# ---------------------------------------------------------------------------

def _get_session_messages(request: Request, session_id: str):
    """Get messages for a session, verifying user ownership. Raises HTTPException on failure."""
    user_id = _get_user_id(request)
    owner = get_owner_of_session(session_id)
    if owner and owner != user_id:
        raise HTTPException(status_code=403, detail="无权操作他人会话")
    if user_id in _conversations and session_id in _conversations[user_id]:
        return _conversations[user_id][session_id], user_id
    raise HTTPException(status_code=404, detail="Session not found")


@router.post("/session/undo")
async def session_undo(payload: dict, request: Request):
    """Undo the last assistant turn: remove the last user+assistant message pair."""
    session_id = payload.get("session_id")
    if not session_id:
        return JSONResponse({"error": "session_id is required"}, status_code=400)

    messages, user_id = _get_session_messages(request, session_id)
    if len(messages) < 2:
        return JSONResponse({"error": "Nothing to undo"}, status_code=400)

    # Remove last assistant + user message pair
    removed_user = None
    while messages:
        last = messages[-1]
        role = last.get("role") if isinstance(last, dict) else None
        if role in ("assistant", "tool"):
            removed = messages.pop()
        elif role == "user":
            removed_user = messages.pop()
            break
        else:
            break

    if removed_user:
        _save_session(session_id, messages, owner=user_id) if _save_session else None
        return {"ok": True, "last_user_message": removed_user if isinstance(removed_user, dict) else {}}

    return {"ok": True, "last_user_message": None}


@router.post("/session/retry")
async def session_retry(payload: dict, request: Request):
    """Retry: undo last assistant turn and return the last user message to resend."""
    session_id = payload.get("session_id")
    if not session_id:
        return JSONResponse({"error": "session_id is required"}, status_code=400)

    messages, user_id = _get_session_messages(request, session_id)
    if not messages:
        return JSONResponse({"error": "Nothing to retry"}, status_code=400)

    # Remove all assistant/tool messages until the last user message
    last_user_content = None
    while messages:
        last = messages[-1]
        role = last.get("role") if isinstance(last, dict) else last.get("role", "")
        if role == "assistant" or role == "tool":
            messages.pop()
        elif role == "user":
            last_user_content = last.get("content", "")
            break
        else:
            break

    if last_user_content:
        _save_session(session_id, messages, owner=user_id) if _save_session else None
        return {"ok": True, "retry_message": last_user_content}

    return {"ok": True, "retry_message": None}


@router.post("/session/rename")
async def session_rename(payload: dict, request: Request):
    """Rename a session. Verifies user ownership."""
    session_id = payload.get("session_id")
    new_name = payload.get("name", "").strip()
    if not session_id or not new_name:
        return JSONResponse({"error": "session_id and name are required"}, status_code=400)
    # Verify ownership
    _get_session_messages(request, session_id)
    return {"ok": True, "name": new_name}


# ── Task Routing API ─────────────────────────────────────────────


@router.get("/routing/status")
async def routing_status():
    """Get current routing status for the frontend LED indicator.

    Returns:
      {
        "tier": "local" | "remote" | "unknown",
        "active_profile": {...} | None,
        "ollama_connected": bool,
      }
    """
    try:
        from services.task_router import get_routing_status
        active = _model_switch.get_active_profile() if _model_switch else None
        return get_routing_status(active_profile=active)
    except Exception as e:
        logger.warning("Routing status failed: %s", e)
        return {"tier": "unknown", "active_profile": None, "ollama_connected": False}


@router.post("/routing/correct")
async def routing_correct(payload: dict):
    """Record a user correction (re-route feedback for learning).

    Request body:
      {
        "original_tier": "local" | "remote",
        "corrected_tier": "local" | "remote",
        "message": "text of the message that was re-routed",
      }
    """
    try:
        from services.correction_store import record_correction
        record_correction(
            original_tier=payload.get("original_tier", "unknown"),
            corrected_tier=payload.get("corrected_tier", "unknown"),
            message_text=payload.get("message", ""),
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
