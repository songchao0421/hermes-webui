"""
Session Manager — manages conversation history, session persistence, and locks.

Owns:
  - conversations: dict[str, list[dict]] — in-memory session store
  - current_session_id: str
  - _session_locks: dict[str, asyncio.Lock]
  - _locks_lock: asyncio.Lock
  - SESSIONS_DIR: Path

Provides:
  - save_session(session_id, messages)
  - load_session(session_id) -> list
  - load_all_sessions()
  - _evict_old_sessions()
  - get_session_lock(session_id) -> asyncio.Lock
"""
import os
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from config import get_sessions_dir

logger = logging.getLogger("hermes_webui")

# ── Directory ────────────────────────────────────────────────────
# Resolved from config at import time (no late injection needed)
SESSIONS_DIR: Path = get_sessions_dir()

# ── In-Memory State ──────────────────────────────────────────────
conversations: dict = {}
current_session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Session Locks ────────────────────────────────────────────────
_session_locks: dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()


async def get_session_lock(session_id: str) -> asyncio.Lock:
    """Get or create a lock for a specific session."""
    async with _locks_lock:
        if session_id not in _session_locks:
            _session_locks[session_id] = asyncio.Lock()
        return _session_locks[session_id]


# ── Eviction ─────────────────────────────────────────────────────

def _evict_old_sessions():
    """Keep at most 100 sessions in memory; evict oldest by session_id (timestamp-based)."""
    MAX_SESSIONS = 100
    if len(conversations) > MAX_SESSIONS:
        sorted_keys = sorted(conversations.keys())
        for key in sorted_keys[:len(conversations) - MAX_SESSIONS]:
            del conversations[key]


# ── Persistence ──────────────────────────────────────────────────

def save_session(session_id: str, messages: list):
    """Save session to disk."""
    try:
        filepath = SESSIONS_DIR / f"{session_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_session(session_id: str) -> list:
    """Load session from disk."""
    try:
        filepath = SESSIONS_DIR / f"{session_id}.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def load_all_sessions():
    """Load all sessions from disk into memory."""
    global conversations
    if SESSIONS_DIR is None:
        return
    try:
        for filepath in SESSIONS_DIR.glob("*.json"):
            session_id = filepath.stem
            messages = load_session(session_id)
            if messages:
                conversations[session_id] = messages
    except Exception:
        pass
