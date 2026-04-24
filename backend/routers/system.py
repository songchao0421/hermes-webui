"""
Hermes WebUI — System Router
==============================
Health, config, and self-update endpoints.
(No legacy Ollama bridge, no WSL bridge, no Hermes CLI detector.)
"""
import asyncio
import json
import os
import shutil
import subprocess

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from config import PROJECT_ROOT
from services.webui_config import load_webui_config, save_webui_config, mask_api_keys

# app is injected by app.py lifespan — only used for version string
app = None

# model_switch is injected by app.py lifespan
model_switch = None

router = APIRouter(tags=["system"])

REPO_API = "https://api.github.com/repos/songchao4218/hermes-webui/commits/main"


# ── Helpers ──────────────────────────────────────────────────────────


def get_local_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()[:7] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def is_git_repo() -> bool:
    return (PROJECT_ROOT / ".git").exists() if PROJECT_ROOT else False


# ── Routes ────────────────────────────────────────────────────────────


@router.get("/health")
async def health_check():
    if app is None:
        return {"status": "ok", "version": "unknown"}
    return {"status": "ok", "version": app.version}


@router.get("/api/config")
async def get_config_api():
    """Get WebUI extended configuration (API keys masked)."""
    cfg = load_webui_config()
    return mask_api_keys(cfg)


@router.put("/api/config")
async def update_config_api(request: Request):
    """Update WebUI extended configuration."""
    body = await request.json()
    cfg = load_webui_config()
    # Deep merge — preserve existing API keys if new value is masked
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
                p["key"] = cur.get("key", "")  # preserve existing key
            merged.append(p)
        routing_new.setdefault("api", {})["providers"] = merged
    cfg["routing"] = {**routing_cur, **routing_new}
    save_webui_config(cfg)
    return {"status": "ok"}


@router.get("/api/update/check")
async def check_update():
    """Check if a newer version is available on GitHub."""
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


@router.post("/api/update/apply")
async def apply_update():
    """Pull latest changes from GitHub and restart."""
    if not is_git_repo():
        raise HTTPException(status_code=400, detail="Not a git repository")

    async def stream_update():
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

            yield f"data: {json.dumps({'done': True, 'message': 'Update complete. Please refresh the page.'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_update(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Model Switching Routes ──────────────────────────────────────────


@router.get("/api/models/profiles")
async def list_models():
    """List all available model profiles."""
    if model_switch is None:
        raise HTTPException(status_code=503, detail="Model switch service not initialized")
    return {"profiles": model_switch.list_profiles()}


@router.post("/api/models/switch")
async def switch_model(request: Request):
    """Switch to a model profile by ID."""
    if model_switch is None:
        raise HTTPException(status_code=503, detail="Model switch service not initialized")
    body = await request.json()
    profile_id = body.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=400, detail="profile_id is required")
    result = model_switch.switch_model(profile_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Switch failed"))
    return result


@router.get("/api/models/active")
async def get_active():
    """Get the currently active model profile."""
    if model_switch is None:
        raise HTTPException(status_code=503, detail="Model switch service not initialized")
    profile = model_switch.get_active_profile()
    if not profile:
        return {"active": None}
    return {"active": profile}


@router.post("/api/models/discover")
async def discover_models():
    """Discover local Ollama models and add them to profiles."""
    if model_switch is None:
        raise HTTPException(status_code=503, detail="Model switch service not initialized")
    discovered = await model_switch.discover_ollama_models()
    count = model_switch.add_discovered_profiles(discovered)
    return {"discovered": count, "profiles": model_switch.list_profiles()}
