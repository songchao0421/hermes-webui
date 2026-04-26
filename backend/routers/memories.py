"""
Hermes WebUI — Memories Router
Manage memory files (SOUL.md, MEMORY.md, USER.md).
"""
import json
import re as _re
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Request
from services.ollama_service import get_ollama_models_async

router = APIRouter(tags=["memories"])

# Module-level globals (injected by app.py)
_bridge = None
_current_session_id = None
_conversations = None
_limiter = None
_get_memory_snapshots_dir = None
_load_session = None

# ── Memory model ────────────────────────────────────────────────
from models import MemoryUpdate


@router.get("/api/memories")
async def get_memories():
    """Get all memory files."""
    return _bridge.get_all_memories()


@router.put("/api/memories/{filename}")
async def update_memory(filename: str, body: MemoryUpdate):
    """Update a memory file."""
    if filename not in ("SOUL.md", "MEMORY.md", "USER.md"):
        raise HTTPException(status_code=400, detail="Invalid memory file")

    if _bridge.write_memory(filename, body.content):
        return {"status": "ok"}
    else:
        raise HTTPException(status_code=500, detail="Failed to write memory")


@router.post("/api/memories/extract")
async def extract_memories(request: Request):
    """
    Use the local LLM to extract memory items from recent conversations.
    Body: { "session_ids": [...], "categories": ["prefs","projects","env"] }
    Returns: { "suggestions": [{"action":"add|update|remove","file":"MEMORY.md","text":"..."}] }
    """
    body = await request.json()
    session_ids = body.get("session_ids", [_current_session_id])
    categories = body.get("categories", ["prefs", "projects", "env"])

    all_messages = []
    for sid in session_ids:
        msgs = _conversations.get(sid) or _load_session(sid)
        all_messages.extend(msgs)

    if not all_messages:
        return {"suggestions": [], "message": "No conversation history found"}

    convo_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:500]}"
        for m in all_messages[-60:]
    )
    cat_desc = {
        "prefs": "user preferences, habits, likes/dislikes",
        "projects": "project names, file paths, technical decisions",
        "env": "system environment, OS, tools, versions",
        "schedule": "dates, deadlines, plans",
    }
    cat_text = ", ".join(cat_desc.get(c, c) for c in categories)

    prompt = f"""Analyze this conversation and extract key facts to remember.
Categories to extract: {cat_text}

Current MEMORY.md content:
{_bridge.read_memory('MEMORY.md')[:1000]}

Current USER.md content:
{_bridge.read_memory('USER.md')[:500]}

Conversation (recent):
{convo_text}

Output a JSON array of memory suggestions. Each item:
{{"action": "add|update|remove", "file": "MEMORY.md|USER.md", "text": "The fact to add/update/remove", "reason": "brief reason"}}

Rules:
- Only include facts that are USEFUL long-term (not transient task details)
- Mark as "update" if the fact already exists but has changed
- Mark as "remove" if fact is now outdated
- Be concise — each fact max 100 characters
- Output ONLY the JSON array, no other text"""

    ollama_url = _bridge.get_ollama_url()
    model = _bridge.get_default_model() or ""
    if not model:
        models = await get_ollama_models_async()
        if models:
            model = models[0]

    if not model:
        return {"suggestions": [], "message": "No AI model available for extraction"}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{ollama_url}/api/chat",
                json={"model": model,
                      "messages": [{"role": "user", "content": prompt}],
                      "stream": False}
            )
            content = resp.json()["message"]["content"]
        match = _re.search(r'\[.*\]', content, _re.DOTALL)
        if match:
            suggestions = json.loads(match.group())
            return {"suggestions": suggestions}
    except Exception as e:
        return {"suggestions": [], "message": f"Extraction failed: {e}"}

    return {"suggestions": [], "message": "Could not parse AI response"}


@router.post("/api/memories/apply")
async def apply_memory_suggestions(request: Request):
    """Apply selected memory suggestions from /api/memories/extract."""
    body = await request.json()
    suggestions = body.get("suggestions", [])
    results = []
    for s in suggestions:
        file = s.get("file", "MEMORY.md")
        if file not in ("MEMORY.md", "USER.md", "SOUL.md"):
            continue
        action = s.get("action", "add")
        text = s.get("text", "").strip()
        if not text:
            continue
        current = _bridge.read_memory(file)
        if action == "add":
            new_content = current.rstrip() + chr(10) + "- " + text + chr(10)
        elif action == "remove":
            lines = [l for l in current.splitlines() if text not in l]
            new_content = chr(10).join(lines)
        elif action == "update":
            new_content = current.rstrip() + chr(10) + "- [Updated] " + text + chr(10)
        else:
            continue
        ok = _bridge.write_memory(file, new_content)
        results.append({"file": file, "action": action, "ok": ok})
    return {"status": "ok", "applied": results}


@router.post("/api/memories/snapshot")
async def memory_snapshot():
    """Create a timestamped snapshot of all memory files."""
    snap_dir = _get_memory_snapshots_dir()
    snap_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = []
    for fname in ("SOUL.md", "MEMORY.md", "USER.md"):
        content = _bridge.read_memory(fname)
        if content:
            snap_file = snap_dir / f"{ts}_{fname}"
            snap_file.write_text(content, encoding="utf-8")
            saved.append(fname)
    return {"status": "ok", "snapshot": ts, "files": saved}
