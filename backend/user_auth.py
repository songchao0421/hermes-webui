"""
Hermes WebUI — User Authentication (Username/Password)
=====================================================
每个员工实名账号登录，自动创建独立的工作目录。
"""

import os
import json
import hashlib
import secrets
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 用户数据存储路径
USERS_DIR = Path.home() / ".hermes" / "hermes-webui" / "users"
USERS_FILE = USERS_DIR / "users.json"

# 员工工作目录根路径
WORKSPACE_ROOT = Path.home() / "Shared" / "员工工作区"


def _ensure_dirs():
    """Ensure user data directories exist."""
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


def _load_users() -> dict:
    """Load all registered users."""
    _ensure_dirs()
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, PermissionError):
            pass
    return {}


def _save_users(users: dict):
    """Save users to disk."""
    _ensure_dirs()
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        USERS_FILE.chmod(0o600)
    except OSError:
        pass


def _hash_password(password: str) -> str:
    """Hash password with SHA-256 + salt."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash."""
    if ":" not in stored:
        return False
    salt, h = stored.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def register_user(username: str, password: str) -> dict:
    """Register a new user. Returns {success, message, workspace?}"""
    _ensure_dirs()
    users = _load_users()

    if not username or not username.strip():
        return {"success": False, "message": "用户名不能为空"}
    if not password or len(password) < 4:
        return {"success": False, "message": "密码至少4位"}
    if username in users:
        return {"success": False, "message": "用户名已存在"}

    # 创建用户工作目录
    workspace = WORKSPACE_ROOT / username
    workspace.mkdir(parents=True, exist_ok=True)

    # 创建子目录
    (workspace / "上传").mkdir(exist_ok=True)
    (workspace / "生成").mkdir(exist_ok=True)

    token = secrets.token_urlsafe(32)
    users[username] = {
        "password": _hash_password(password),
        "token": token,
        "created_at": __import__("datetime").datetime.now().isoformat(),
        "workspace": str(workspace),
    }
    _save_users(users)

    logger.info("新用户注册: %s", username)
    return {
        "success": True,
        "message": "注册成功",
        "token": token,
        "workspace": str(workspace),
    }


def login_user(username: str, password: str) -> dict:
    """Login. Returns {success, message, token?, workspace?}"""
    users = _load_users()

    if username not in users:
        return {"success": False, "message": "用户名或密码错误"}

    if not _verify_password(password, users[username]["password"]):
        return {"success": False, "message": "用户名或密码错误"}

    # 刷新 token
    token = secrets.token_urlsafe(32)
    users[username]["token"] = token
    _save_users(users)

    # 确保工作目录存在
    workspace = Path(users[username]["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "上传").mkdir(exist_ok=True)
    (workspace / "生成").mkdir(exist_ok=True)

    return {
        "success": True,
        "message": "登录成功",
        "token": token,
        "username": username,
        "workspace": str(workspace),
    }


def verify_token(token: str) -> Optional[str]:
    """Verify a token and return the username. Returns None if invalid."""
    users = _load_users()
    for username, data in users.items():
        if data.get("token") == token:
            return username
    return None


def get_user_workspace(username: str) -> Optional[Path]:
    """Get user's workspace directory."""
    users = _load_users()
    if username not in users:
        return None
    return Path(users[username]["workspace"])


def list_users() -> list:
    """List all registered usernames (admin use)."""
    users = _load_users()
    return sorted(users.keys())
