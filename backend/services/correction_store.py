"""
correction_store — SQLite-backed routing correction memory.

Stores user corrections (re-route events) and learned keyword→tier patterns
so the router can replay them on startup and improve routing accuracy over time.

Schema (corrections table):
  original  — original user request text
  corrected — corrected/adjusted request text
  message   — the response or message that triggered the correction

File:
  ~/.hermes/hermes-webui/corrections.db
"""

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import get_data_dir

logger = logging.getLogger(__name__)

# ── Schema ──────────────────────────────────────────────────────────────────

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS corrections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    original    TEXT NOT NULL,
    corrected   TEXT NOT NULL,
    message     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS keyword_patterns (
    keyword     TEXT PRIMARY KEY,
    local_wt    INTEGER NOT NULL DEFAULT 0,
    remote_wt   INTEGER NOT NULL DEFAULT 0
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_corrections_created
    ON corrections(created_at);
CREATE INDEX IF NOT EXISTS idx_keyword_patterns_wt
    ON keyword_patterns(local_wt, remote_wt);
"""


# ── Singleton connection ────────────────────────────────────────────────────

_conn: Optional[sqlite3.Connection] = None


def _get_db_path() -> Path:
    """Return the path to the SQLite database file (in get_data_dir())."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "corrections.db"


def _get_conn() -> sqlite3.Connection:
    """Get or create the singleton SQLite connection."""
    global _conn
    if _conn is None:
        db_path = _get_db_path()
        logger.info("Opening correction store: %s", db_path)
        _conn = sqlite3.connect(str(db_path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_CREATE_TABLES)
        _conn.executescript(_INDEXES)
        # WAL mode for better concurrent reads
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def close():
    """Close the database connection (call on shutdown)."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
        logger.info("Correction store closed.")


# ── Public API ──────────────────────────────────────────────────────────────


def record_correction(
    original_tier: str,
    corrected_tier: str,
    message_text: str,
):
    """Record a user correction (re-route event) and update keyword patterns.

    Args:
        original_tier: The tier that was originally chosen ("local" or "remote").
        corrected_tier: The tier the user corrected to ("local" or "remote").
        message_text: The user's original message text.
    """
    conn = _get_conn()
    now = datetime.now(timezone.utc).isoformat()

    # Insert the correction record
    conn.execute(
        "INSERT INTO corrections (original, corrected, message, created_at) VALUES (?, ?, ?, ?)",
        (original_tier, corrected_tier, message_text[:200], now),
    )

    # Extract keywords — split by non-word boundaries, then extract 2-4 char n-grams
    words = set()
    # English words (2+ chars)
    words.update(re.findall(r"[a-z]{2,}", message_text.lower()))
    # Chinese: split by non-Chinese boundaries, then extract 2-4 char substrings
    chinese_segments = re.findall(r"[\u4e00-\u9fff]+", message_text)
    for seg in chinese_segments:
        seg_len = len(seg)
        for i in range(seg_len - 1):
            for j in (2, 3, 4):
                if i + j <= seg_len:
                    words.add(seg[i:i+j].lower())
    for w in words:
        conn.execute(
            """INSERT INTO keyword_patterns (keyword, local_wt, remote_wt)
               VALUES (?, 0, 0)
               ON CONFLICT(keyword) DO NOTHING""",
            (w,),
        )
        conn.execute(
            f"UPDATE keyword_patterns SET {corrected_tier}_wt = {corrected_tier}_wt + 1 WHERE keyword = ?",
            (w,),
        )

    conn.commit()
    logger.debug("Recorded correction: %s -> %s (keywords: %d)", original_tier, corrected_tier, len(words))


def get_patterns() -> dict[str, dict[str, int]]:
    """Return all learned keyword→tier patterns.

    Returns:
        {keyword: {"local": N, "remote": N}}
    """
    conn = _get_conn()
    rows = conn.execute("SELECT keyword, local_wt, remote_wt FROM keyword_patterns").fetchall()
    return {r["keyword"]: {"local": r["local_wt"], "remote": r["remote_wt"]} for r in rows}


def get_correction_history(limit: int = 50) -> list[dict]:
    """Return the most recent corrections.

    Args:
        limit: Max records to return.

    Returns:
        [{"id", "original", "corrected", "message", "created_at"}, ...]
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM corrections ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def score_message(message_text: str) -> Optional[str]:
    """Score a message against learned patterns and suggest a tier.

    Uses simple keyword weight voting:
      total_local  = sum(local_wt for keywords in message)
      total_remote = sum(remote_wt for keywords in message)
      If one side has >= 2x the other AND >= 3 total weight, suggest it.

    Args:
        message_text: The user's message.

    Returns:
        "local" | "remote" | None (if patterns are insufficient).
    """
    conn = _get_conn()
    words = set()
    # English words (2+ chars)
    words.update(re.findall(r"[a-z]{2,}", message_text.lower()))
    # Chinese: 2-4 char n-grams from segments
    chinese_segments = re.findall(r"[\u4e00-\u9fff]+", message_text)
    for seg in chinese_segments:
        seg_len = len(seg)
        for i in range(seg_len - 1):
            for j in (2, 3, 4):
                if i + j <= seg_len:
                    words.add(seg[i:i+j].lower())
    if not words:
        return None

    placeholders = ",".join("?" for _ in words)
    rows = conn.execute(
        f"SELECT keyword, local_wt, remote_wt FROM keyword_patterns WHERE keyword IN ({placeholders})",
        list(words),
    ).fetchall()

    total_local = sum(r["local_wt"] for r in rows)
    total_remote = sum(r["remote_wt"] for r in rows)
    total = total_local + total_remote

    if total < 3:
        return None  # not enough data

    if total_local >= total_remote * 2:
        return "local"
    if total_remote >= total_local * 2:
        return "remote"
    return None
