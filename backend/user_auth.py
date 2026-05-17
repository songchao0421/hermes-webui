"""
Hermes WebUI — User Authentication (Username/Password)
=====================================================
每个员工实名账号登录，自动创建独立的工作目录。

v2.1: bcrypt 密码哈希 + 登录失败锁定 (5次/15分钟)
"""

import os
import json
import secrets
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import bcrypt

logger = logging.getLogger(__name__)

# ── 用户数据存储路径 ─────────────────────────────────────────────────
USERS_DIR = Path.home() / ".hermes" / "hermes-webui" / "users"
USERS_FILE = USERS_DIR / "users.json"

# 员工工作目录根路径
WORKSPACE_ROOT = Path.home() / "Shared" / "员工工作区"

# ── 安全参数 ─────────────────────────────────────────────────────────
MAX_LOGIN_ATTEMPTS = 5          # 最大失败次数
LOCKOUT_DURATION_SEC = 15 * 60  # 锁定时间（秒）
MIN_PASSWORD_LENGTH = 8         # 最小密码长度
PASSWORD_HISTORY_SIZE = 5       # 密码历史保留条数（禁止循环复用）
PASSWORD_EXPIRE_DAYS = 90       # 密码过期天数
TOKEN_TTL_SEC = 2 * 3600        # Token 有效期（2 小时）

# ── 特性开关 ─────────────────────────────────────────────────────────
# 注册功能默认开放（内网场景）。如需关闭:
#   export HERMES_REGISTRATION_ENABLED=false
REGISTRATION_ENABLED = os.environ.get("HERMES_REGISTRATION_ENABLED", "true").lower() in ("1", "true", "yes")


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
        logger.warning("无法设置用户文件权限为 600（非 POSIX 系统属正常情况）: %s", USERS_FILE)


# ── 密码哈希 (bcrypt) ────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Hash password with bcrypt. 返回 bcrypt 格式字符串."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash.

    兼容旧版 SHA-256 格式 (salt:hash) 和 bcrypt 格式 ($2b$...)
    如果检测到旧格式，验证成功后会在 login_user 中自动升级。
    """
    if stored.startswith("$2"):
        # bcrypt 格式
        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
    # 旧版 SHA-256 格式 (兼容)
    if ":" in stored:
        import hashlib
        salt, h = stored.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    return False


def _is_legacy_hash(stored: str) -> bool:
    """检查是否是旧版 SHA-256 格式的密码哈希。"""
    return not stored.startswith("$2")


# ── 登录锁定 ─────────────────────────────────────────────────────────

def _check_lockout(user_data: dict) -> Optional[str]:
    """检查用户是否被锁定。返回 None 表示未锁定，否则返回锁定原因字符串。"""
    failures = user_data.get("login_failures", 0)
    last_failure_ts = user_data.get("last_failure_ts", 0)

    if failures >= MAX_LOGIN_ATTEMPTS:
        elapsed = time.time() - last_failure_ts
        if elapsed < LOCKOUT_DURATION_SEC:
            remaining = int(LOCKOUT_DURATION_SEC - elapsed)
            minutes = remaining // 60
            seconds = remaining % 60
            return f"账号已锁定，请 {minutes} 分 {seconds} 秒后重试"
        else:
            # 锁定时间已过，自动解除
            user_data["login_failures"] = 0
            user_data["last_failure_ts"] = 0
    return None


def _record_login_failure(user_data: dict):
    """记录一次登录失败。"""
    user_data["login_failures"] = user_data.get("login_failures", 0) + 1
    user_data["last_failure_ts"] = time.time()


def _reset_login_failures(user_data: dict):
    """登录成功后重置失败计数。"""
    user_data["login_failures"] = 0
    user_data["last_failure_ts"] = 0


# ── 注册 / 登录 / 验证 ──────────────────────────────────────────────

def register_user(username: str, password: str) -> dict:
    """Register a new user. Returns {success, message, workspace?}"""
    # ── 注册开关检查 ──
    if not REGISTRATION_ENABLED:
        return {"success": False, "message": "注册功能未开放，请联系管理员添加账号"}
    _ensure_dirs()
    users = _load_users()

    if not username or not username.strip():
        return {"success": False, "message": "用户名不能为空"}
    username = username.strip()
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return {"success": False, "message": f"密码至少{MIN_PASSWORD_LENGTH}位"}
    if username in users:
        return {"success": False, "message": "用户名已存在"}

    # 创建用户工作目录
    workspace = WORKSPACE_ROOT / username
    workspace.mkdir(parents=True, exist_ok=True)

    # 创建子目录
    (workspace / "上传").mkdir(exist_ok=True)
    (workspace / "生成").mkdir(exist_ok=True)

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    hashed_pw = _hash_password(password)
    users[username] = {
        "password": hashed_pw,
        "token": token,
        "token_issued_at": time.time(),
        "created_at": now,
        "workspace": str(workspace),
        "enabled": True,
        "login_failures": 0,
        "last_failure_ts": 0,
        "last_login_at": None,
        "last_active_at": time.time(),
        "role": "user",
        "password_changed_at": time.time(),
        "password_history": [hashed_pw],
    }
    _save_users(users)

    logger.info("用户注册: %s", username)
    return {
        "success": True,
        "message": "注册成功",
        "token": token,
        "workspace": str(workspace),
    }


def login_user(username: str, password: str) -> dict:
    """Login. Returns {success, message, token?, workspace?}"""
    users = _load_users()
    username = username.strip()

    if username not in users:
        return {"success": False, "message": "用户名或密码错误"}

    user_data = users[username]

    # 检查账号是否被管理员停用
    if not user_data.get("enabled", True):
        return {"success": False, "message": "账号已被停用，请联系管理员"}

    # 检查是否被锁定
    lock_msg = _check_lockout(user_data)
    if lock_msg:
        return {"success": False, "message": lock_msg}

    # 验证密码
    if not _verify_password(password, user_data["password"]):
        _record_login_failure(user_data)
        _save_users(users)

        failures = user_data["login_failures"]
        remaining = MAX_LOGIN_ATTEMPTS - failures
        if remaining <= 0:
            return {"success": False, "message": f"密码错误，账号已锁定 {LOCKOUT_DURATION_SEC // 60} 分钟"}
        return {"success": False, "message": f"用户名或密码错误（还剩 {remaining} 次尝试）"}
    else:
        _reset_login_failures(user_data)

    # 密码哈希自动升级：旧格式 → bcrypt
    if _is_legacy_hash(user_data["password"]):
        user_data["password"] = _hash_password(password)
        logger.info("密码哈希已升级为 bcrypt: %s", username)

    # 刷新 token（旧 token 作废）
    now_ts = time.time()
    token = secrets.token_urlsafe(32)
    user_data["token"] = token
    user_data["token_issued_at"] = now_ts
    user_data["last_active_at"] = now_ts
    user_data["last_login_at"] = datetime.now(timezone.utc).isoformat()
    _save_users(users)

    # 确保工作目录存在
    workspace = Path(user_data["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "上传").mkdir(exist_ok=True)
    (workspace / "生成").mkdir(exist_ok=True)

    logger.info("用户登录: %s", username)

    result = {
        "success": True,
        "message": "登录成功",
        "token": token,
        "username": username,
        "workspace": str(workspace),
    }

    # 检查密码是否过期
    pwd_changed = user_data.get("password_changed_at", 0)
    pwd_age_days = (now_ts - pwd_changed) / 86400
    if pwd_age_days >= PASSWORD_EXPIRE_DAYS:
        result["password_expired"] = True
        result["message"] = f"密码已过期（{int(pwd_age_days)} 天），请修改密码"

    return result


# ── 登出 ───────────────────────────────────────────────────────────────

def logout_user(username: str) -> dict:
    """服务端登出：清除当前 token，强制该设备下线。

    注意：只清除当前 token，不影响后续登录生成的新 token。
    如果用户在其他设备上也有登录，其他设备的 token 仍有效。
    """
    users = _load_users()
    if username not in users:
        return {"success": False, "message": "用户不存在"}
    if not users[username].get("enabled", True):
        users[username]["token"] = ""
        users[username]["token_issued_at"] = 0
        _save_users(users)
        return {"success": True, "message": "已登出"}

    users[username]["token"] = ""
    users[username]["token_issued_at"] = 0
    _save_users(users)
    logger.info("用户登出: %s", username)
    return {"success": True, "message": "已登出"}


def verify_token(token: str) -> Optional[str]:
    """Verify a token and return the username. Returns None if invalid.

    只验证启用中的账号。不检查 TTL（TTL 由 token 过期检查单独处理）。
    """
    if not token:
        return None
    users = _load_users()
    # 反向索引：token → username（O(1) 查找替代 O(n) 扫描）
    token_index = {data.get("token"): username for username, data in users.items() if data.get("token")}
    username = token_index.get(token)
    if username and users[username].get("enabled", True):
        return username
    return None


def check_token_expired(token: str) -> bool:
    """检查 token 是否过期（超过 TOKEN_TTL_SEC 未活动）。

    返回 True 表示已过期，False 表示有效。
    """
    if not token:
        return True
    users = _load_users()
    token_index = {data.get("token"): username for username, data in users.items() if data.get("token")}
    username = token_index.get(token)
    if username:
        last_active = users[username].get("last_active_at", 0)
        return (time.time() - last_active) >= TOKEN_TTL_SEC
    return True


def renew_token_activity(token: str):
    """更新 token 的最后活动时间（每次 API 调用时续期）。"""
    if not token:
        return
    users = _load_users()
    token_index = {data.get("token"): username for username, data in users.items() if data.get("token")}
    username = token_index.get(token)
    if username:
        users[username]["last_active_at"] = time.time()
        _save_users(users)


def get_user_workspace(username: str) -> Optional[Path]:
    """Get user's workspace directory."""
    users = _load_users()
    if username not in users:
        return None
    return Path(users[username]["workspace"])


# ── 修改密码 ─────────────────────────────────────────────────────────

def change_password(username: str, old_password: str, new_password: str) -> dict:
    """用户自行修改密码。

    检查：旧密码正确、新密码长度、新密码不与最近 1 次重复。
    """
    users = _load_users()
    if username not in users:
        return {"success": False, "message": "用户不存在"}

    user_data = users[username]
    if not user_data.get("enabled", True):
        return {"success": False, "message": "账号已被停用"}

    # 验证旧密码
    if not _verify_password(old_password, user_data["password"]):
        return {"success": False, "message": "旧密码不正确"}

    if not new_password or len(new_password) < MIN_PASSWORD_LENGTH:
        return {"success": False, "message": f"新密码至少{MIN_PASSWORD_LENGTH}位"}

    # 密码历史检查：不能与最近 PASSWORD_HISTORY_SIZE 次相同
    history = user_data.get("password_history", [])
    if history:
        for old_hash in history[:PASSWORD_HISTORY_SIZE]:
            if _verify_password(new_password, old_hash):
                return {"success": False, "message": f"新密码不能与最近{PASSWORD_HISTORY_SIZE}次使用的密码相同"}

    # 哈希新密码
    new_hash = _hash_password(new_password)

    # 更新密码历史（保留最近 PASSWORD_HISTORY_SIZE 条旧密码，加新密码共 PASSWORD_HISTORY_SIZE+1 条）
    user_data["password_history"] = ([user_data["password"]] + history)[:PASSWORD_HISTORY_SIZE + 1]
    user_data["password"] = new_hash
    user_data["password_changed_at"] = time.time()

    # 清除 token 强制重新登录
    user_data["token"] = ""
    _save_users(users)

    logger.info("密码已修改: %s", username)
    return {"success": True, "message": "密码修改成功，请重新登录"}


# ── 管理员功能 ───────────────────────────────────────────────────────

def list_users() -> list:
    """List all registered users with status (admin use)."""
    users = _load_users()
    result = []
    for username, data in users.items():
        result.append({
            "username": username,
            "enabled": data.get("enabled", True),
            "created_at": data.get("created_at", ""),
            "last_login_at": data.get("last_login_at"),
            "login_failures": data.get("login_failures", 0),
            "workspace": data.get("workspace", ""),
            "role": data.get("role", "user"),
        })
    return sorted(result, key=lambda u: u["username"])


def set_user_enabled(username: str, enabled: bool) -> dict:
    """启用或停用用户账号。"""
    users = _load_users()
    if username not in users:
        return {"success": False, "message": "用户不存在"}

    users[username]["enabled"] = enabled
    if not enabled:
        # 停用时清除 token，强制下线
        users[username]["token"] = ""
    _save_users(users)

    action = "启用" if enabled else "停用"
    logger.info("管理员%s用户: %s", action, username)
    return {"success": True, "message": f"已{action}用户 {username}"}


def admin_reset_password(username: str, new_password: str) -> dict:
    """管理员重置用户密码。"""
    users = _load_users()
    if username not in users:
        return {"success": False, "message": "用户不存在"}

    if not new_password or len(new_password) < MIN_PASSWORD_LENGTH:
        return {"success": False, "message": f"密码至少{MIN_PASSWORD_LENGTH}位"}

    new_hash = _hash_password(new_password)
    # 更新密码历史（与 change_password 一致）
    history = users[username].get("password_history", [])
    users[username]["password_history"] = ([users[username]["password"]] + history)[:PASSWORD_HISTORY_SIZE + 1]
    users[username]["password"] = new_hash
    users[username]["password_changed_at"] = time.time()
    users[username]["token"] = ""  # 清除 token，强制重新登录
    users[username]["token_issued_at"] = 0
    users[username]["login_failures"] = 0
    users[username]["last_failure_ts"] = 0
    _save_users(users)

    logger.info("管理员重置密码: %s", username)
    return {"success": True, "message": f"已重置 {username} 的密码"}
