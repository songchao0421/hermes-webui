"""
System Service — health, config, update logic.

Extracted from routers/system.py so routing is thin and testable.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, AsyncGenerator

import httpx
from config import PROJECT_ROOT
from services.webui_config import load_webui_config, save_webui_config, mask_api_keys

logger = logging.getLogger("hermes_webui.system_service")

REPO_API = "https://api.github.com/repos/songchao0421/hermes-webui/commits/main"


# ── Git helpers ─────────────────────────────────────────────────────────────


def get_local_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def is_git_repo() -> bool:
    return (PROJECT_ROOT / ".git").exists() if PROJECT_ROOT else False


# ── Version ─────────────────────────────────────────────────────────────────


def get_version(app) -> str:
    try:
        return app.version
    except AttributeError:
        return "0.0.0"


# ─── Config ─────────────────────────────────────────────────────────────────


def get_config() -> Dict[str, Any]:
    cfg = load_webui_config()
    return mask_api_keys(cfg)


def update_config(body: Dict[str, Any]) -> None:
    """Deep-merge incoming config, preserving masked API keys."""
    cfg = load_webui_config()

    routing_new = body.get("routing", {})
    routing_cur = cfg.get("routing", {})

    new_providers = routing_new.get("api", {}).get("providers", None)
    if new_providers is not None:
        cur_providers = {p["id"]: p for p in routing_cur.get("api", {}).get("providers", [])}
        merged = []
        for p in new_providers:
            pid = p.get("id", "")
            cur = cur_providers.get(pid, {})
            key = p.get("key", "")
            if "****" in key or not key:
                p["key"] = cur.get("key", "")
            merged.append(p)
        routing_new.setdefault("api", {})["providers"] = merged

    cfg["routing"] = {**routing_cur, **routing_new}
    save_webui_config(cfg)


# ── Update check ────────────────────────────────────────────────────────────


async def check_update() -> Dict[str, Any]:
    if not is_git_repo():
        return {"has_update": False, "error": "Not a git repository"}

    local_commit = get_local_commit()

    try:
        proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or \
                os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY")
        client_kwargs = {"timeout": 10}
        if proxy:
            client_kwargs["proxy"] = proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(
                REPO_API,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                return {"has_update": False, "error": f"GitHub API error: {resp.status_code}"}

            data = resp.json()
            remote_sha = data.get("sha", "")[:7]
            remote_message = data.get("commit", {}).get("message", "").split("\n")[0]
            remote_date = data.get("commit", {}).get("author", {}).get("date", "")[:10]
            has_update = remote_sha != local_commit and local_commit != "unknown"

            return {
                "has_update": has_update,
                "local_commit": local_commit,
                "remote_commit": remote_sha,
                "remote_message": remote_message,
                "remote_date": remote_date,
            }
    except Exception as e:
        return {"has_update": False, "error": str(e)}


async def stream_update() -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted log lines:
      data: {"log": "..."}
      data: {"error": "..."}
      data: {"restart": true, "host": "...", "port": ...}
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "pull", "--ff-only",
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc.stdout:
            yield f"data: {json.dumps({'log': line.decode('utf-8', errors='replace').rstrip()})}\n\n"
        await proc.wait()

        if proc.returncode != 0:
            yield f"data: {json.dumps({'error': 'git pull failed'})}\n\n"
            return

        pip_cmd = "pip3" if shutil.which("pip3") else "pip"
        req_file = str(PROJECT_ROOT / "backend" / "requirements.txt")
        proc2 = await asyncio.create_subprocess_exec(
            pip_cmd, "install", "-r", req_file, "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc2.stdout:
            yield f"data: {json.dumps({'log': line.decode('utf-8', errors='replace').rstrip()})}\n\n"
        await proc2.wait()

        yield f"data: {json.dumps({'log': 'Update complete. Restarting server...'})}\n\n"

        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "8080"))

        yield f"data: {json.dumps({'log': f'Restarting on {host}:{port}...'})}\n\n"

        launch_script = str(PROJECT_ROOT / "backend" / "app.py")
        cmd = [sys.executable, launch_script, "--host", host, "--port", str(port)]

        try:
            import auth as _auth
            if not _auth.is_auth_enabled():
                cmd.append("--no-auth")
        except Exception:
            pass

        try:
            import app as _app_mod
            if getattr(_app_mod, 'WSL_MODE', False):
                cmd.append("--wsl-mode")
        except Exception:
            pass

        subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT / "backend"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        yield f"data: {json.dumps({'restart': True, 'host': host, 'port': port})}\n\n"

        # Exit current process (give SSE a moment to flush)
        os._exit(0)

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
