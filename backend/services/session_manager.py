"""
Session Manager — manages conversation history, session persistence, and locks.

v2.2: 多用户隔离 + 磁盘 AES-256-GCM 加密存储。

使用:
  - conversations: defaultdict[dict]  — {user_id: {session_id: [messages]}}
  - current_session_id: str — 全局变量，前端需要时通过 API 设置
  - session_owners: dict[session_id, user_id] — 反向索引
"""

import os
import json
import asyncio
import hashlib
import logging
import secrets as _secrets
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import get_sessions_dir, get_data_dir

logger = logging.getLogger("hermes_webui")

# ── Directory ────────────────────────────────────────────────────
SESSIONS_DIR: Path = get_sessions_dir()

# ── In-Memory State ──────────────────────────────────────────────
# conversations 现在是双层字典: {user_id: {session_id: [messages]}}
conversations: dict = defaultdict(dict)

# session_owners 是反向索引: session_id -> user_id
session_owners: dict[str, str] = {}

# 当前活跃 session ID（兼容旧代码，前端用）
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


# ── Session Ownership Helpers ────────────────────────────────────

def get_sessions_for_user(user_id: str) -> dict:
    """获取某个用户的所有会话。返回 {session_id: [messages]}。"""
    return conversations.get(user_id, {})


def get_owner_of_session(session_id: str) -> Optional[str]:
    """获取某个 session 的所属用户。"""
    return session_owners.get(session_id)


def set_session_owner(session_id: str, user_id: str):
    """设置某个 session 的所属用户。"""
    session_owners[session_id] = user_id


def remove_session_owner(session_id: str):
    """删除 session 归属记录。"""
    session_owners.pop(session_id, None)


# ── Eviction ─────────────────────────────────────────────────────

def _evict_old_sessions():
    """Keep at most 200 sessions across all users; evict oldest by session_id."""
    MAX_SESSIONS = 200
    total = sum(len(sess) for sess in conversations.values())
    if total > MAX_SESSIONS:
        # 收集所有 session_id -> (user_id, timestamp_str)
        all_sessions = []
        for uid, sessions in conversations.items():
            for sid in sessions.keys():
                all_sessions.append((sid, uid))
        # 按 session_id 排序（时间戳格式），最旧的在前
        all_sessions.sort()
        to_remove = total - MAX_SESSIONS
        for sid, uid in all_sessions[:to_remove]:
            del conversations[uid][sid]
            remove_session_owner(sid)
            # 清理空用户
            if not conversations[uid]:
                del conversations[uid]


# ── Session Encryption (AES-256-GCM) ────────────────────────────

ENCRYPTION_KEY_FILE = get_data_dir() / ".session_key"


def _get_or_create_encryption_key() -> bytes:
    """Get or create a persistent AES-256 key for session encryption."""
    if ENCRYPTION_KEY_FILE.exists():
        return ENCRYPTION_KEY_FILE.read_bytes()
    key = AESGCM.generate_key(bit_length=256)  # 32 bytes
    ENCRYPTION_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENCRYPTION_KEY_FILE.write_bytes(key)
    try:
        ENCRYPTION_KEY_FILE.chmod(0o600)
    except OSError:
        logger.warning("无法设置加密密钥文件权限为 600（非 POSIX 系统属正常情况）: %s", ENCRYPTION_KEY_FILE)
    return key


_ENCRYPTION_KEY: Optional[bytes] = None


def _get_aesgcm() -> AESGCM:
    global _ENCRYPTION_KEY
    if _ENCRYPTION_KEY is None:
        _ENCRYPTION_KEY = _get_or_create_encryption_key()
    return AESGCM(_ENCRYPTION_KEY)


# ── Persistence ──────────────────────────────────────────────────

def save_session(session_id: str, messages: list, owner: Optional[str] = None):
    """Save session to disk with AES-256-GCM encryption.

    File format: binary file with 12-byte nonce + ciphertext.
    Legacy .json files are left in place (no migration — delete old manually).
    """
    try:
        filepath = SESSIONS_DIR / f"{session_id}.enc"
        payload = json.dumps({
            "owner": owner or get_owner_of_session(session_id),
            "messages": messages,
        }, ensure_ascii=False).encode("utf-8")

        nonce = _secrets.token_bytes(12)
        aesgcm = _get_aesgcm()
        ciphertext = aesgcm.encrypt(nonce, payload, None)

        with open(filepath, "wb") as f:
            f.write(nonce + ciphertext)  # 12 + len(payload) + 16 (tag)
    except Exception:
        pass


def load_session(session_id: str) -> list:
    """Load session messages from disk (returns empty list if not found).

    Tries .enc format first (AES-256-GCM encrypted), falls back to .json (legacy plaintext).
    """
    # Try encrypted format first
    enc_path = SESSIONS_DIR / f"{session_id}.enc"
    if enc_path.exists():
        try:
            raw = enc_path.read_bytes()
            if len(raw) < 28:  # 12 nonce + 16 tag minimum
                return []
            nonce = raw[:12]
            ciphertext = raw[12:]
            aesgcm = _get_aesgcm()
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            data = json.loads(plaintext.decode("utf-8"))
            owner = data.get("owner")
            if owner:
                set_session_owner(session_id, owner)
            return data.get("messages", [])
        except Exception:
            return []

    # Legacy .json fallback
    filepath = SESSIONS_DIR / f"{session_id}.json"
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                owner = data.get("owner")
                if owner:
                    set_session_owner(session_id, owner)
                return data.get("messages", [])
            return data if isinstance(data, list) else []
        except Exception:
            pass
    return []


def load_all_sessions():
    """Load all sessions from disk into memory, grouped by owner.

    Reads both .enc (encrypted) and .json (legacy plaintext) files.
    """
    global conversations
    if SESSIONS_DIR is None:
        return

    def _load_from_path(path_obj: Path) -> Optional[tuple[str, list]]:
        session_id = path_obj.stem
        if path_obj.suffix == ".enc":
            try:
                raw = path_obj.read_bytes()
                if len(raw) < 28:
                    return None
                nonce = raw[:12]
                ciphertext = raw[12:]
                aesgcm = _get_aesgcm()
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                data = json.loads(plaintext.decode("utf-8"))
                owner = data.get("owner", "unknown")
                return owner, data.get("messages", [])
            except Exception:
                return None
        elif path_obj.suffix == ".json":
            try:
                with open(path_obj, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                return None
            if isinstance(data, dict) and "owner" in data:
                return data.get("owner", "unknown"), data.get("messages", [])
            return "unknown", data if isinstance(data, list) else []
        return None

    try:
        for filepath in sorted(SESSIONS_DIR.glob("*.enc")):
            result = _load_from_path(filepath)
            if result and result[1]:
                owner, messages = result
                set_session_owner(filepath.stem, owner)
                conversations[owner][filepath.stem] = messages
    except Exception:
        pass

    try:
        # Legacy .json fallback (loaded after .enc, so encrypted wins if both exist)
        for filepath in sorted(SESSIONS_DIR.glob("*.json")):
            if (SESSIONS_DIR / f"{filepath.stem}.enc").exists():
                continue  # Skip if encrypted version exists
            result = _load_from_path(filepath)
            if result and result[1]:
                owner, messages = result
                set_session_owner(filepath.stem, owner)
                conversations[owner][filepath.stem] = messages
    except Exception:
        pass
