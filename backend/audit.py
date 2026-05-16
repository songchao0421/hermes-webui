"""
Hermes WebUI — 审计日志模块
============================
结构化 JSON 审计日志，记录所有安全敏感操作。

日志位置: ~/.hermes/hermes-webui/audit/
格式: 每行一条 JSON 记录
轮转: 按日期分文件 (audit_2026-05-16.jsonl)

记录事件:
  - login_success / login_failure / login_locked
  - register / password_reset
  - file_download / file_upload
  - memory_write / memory_snapshot
  - conversation_access / session_create / session_delete
  - user_enable / user_disable
  - admin_action
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from config import get_data_dir

logger = logging.getLogger(__name__)

AUDIT_DIR = get_data_dir() / "audit"
AUDIT_RETENTION_DAYS = 90  # 审计日志保留天数


def _ensure_audit_dir():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _audit_log_file() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return AUDIT_DIR / f"audit_{today}.jsonl"


def _clean_old_logs():
    """删除超过 AUDIT_RETENTION_DAYS 天的审计日志文件。"""
    if not AUDIT_DIR.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=AUDIT_RETENTION_DAYS)
    for filepath in AUDIT_DIR.glob("audit_*.jsonl"):
        try:
            # 从文件名提取日期: audit_2026-05-16.jsonl → 2026-05-16
            date_str = filepath.stem.replace("audit_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff:
                filepath.unlink()
                logger.info("已删除过期审计日志: %s", filepath.name)
        except (ValueError, OSError):
            pass


def log_event(
    event: str,
    username: Optional[str] = None,
    ip: Optional[str] = None,
    details: Optional[dict] = None,
):
    """写入一条审计记录。

    Args:
        event: 事件类型 (e.g. "login_success", "file_download")
        username: 触发事件的用户
        ip: 客户端 IP
        details: 事件相关数据字典
    """
    _ensure_audit_dir()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "username": username or "anonymous",
        "ip": ip or "unknown",
        "details": details or {},
    }
    try:
        with open(_audit_log_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("审计日志写入失败: %s", exc)

    # 每次写入后抽样清理（约 1/20 概率触发清理，避免每次遍历目录）
    import random
    if random.randint(1, 20) == 1:
        _clean_old_logs()


# ── Shortcut helpers ──────────────────────────────────────────────────

def audit_login_success(username: str, ip: Optional[str] = None):
    log_event("login_success", username=username, ip=ip)


def audit_login_failure(username: str, reason: str, ip: Optional[str] = None):
    log_event("login_failure", username=username, ip=ip, details={"reason": reason})


def audit_login_locked(username: str, ip: Optional[str] = None):
    log_event("login_locked", username=username, ip=ip,
              details={"message": f"Account locked after {5} failed attempts"})


def audit_register(username: str, ip: Optional[str] = None):
    log_event("register", username=username, ip=ip)


def audit_password_reset(admin: str, target_user: str, ip: Optional[str] = None):
    log_event("password_reset", username=admin, ip=ip,
              details={"target_user": target_user})


def audit_file_download(username: str, filename: str, source: str, ip: Optional[str] = None):
    log_event("file_download", username=username, ip=ip,
              details={"filename": filename, "source": source})


def audit_file_upload(username: str, filename: str, size: int, ip: Optional[str] = None):
    log_event("file_upload", username=username, ip=ip,
              details={"filename": filename, "size": size})


def audit_memory_write(username: str, filename: str, ip: Optional[str] = None):
    log_event("memory_write", username=username, ip=ip,
              details={"file": filename})


def audit_memory_snapshot(username: str, files: list, ip: Optional[str] = None):
    log_event("memory_snapshot", username=username, ip=ip,
              details={"files": files})


def audit_conversation_access(username: str, session_id: str, ip: Optional[str] = None):
    log_event("conversation_access", username=username, ip=ip,
              details={"session_id": session_id})


def audit_session_create(username: str, session_id: str, ip: Optional[str] = None):
    log_event("session_create", username=username, ip=ip,
              details={"session_id": session_id})


def audit_session_delete(username: str, session_id: str, ip: Optional[str] = None):
    log_event("session_delete", username=username, ip=ip,
              details={"session_id": session_id})


def audit_user_disable(username: str, target_user: str, ip: Optional[str] = None):
    log_event("user_disable", username=username, ip=ip,
              details={"target_user": target_user})


def audit_user_enable(username: str, target_user: str, ip: Optional[str] = None):
    log_event("user_enable", username=username, ip=ip,
              details={"target_user": target_user})
