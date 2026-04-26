"""
Hermes WebUI — System Router (thin)

Routes delegate to services/system_service.py for business logic.
Model switching routes grouped here.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import services.system_service as svc
from services.system_service import get_version

# app is injected by app.py lifespan — only used for version string
app = None

# model_switch is injected by app.py lifespan
model_switch = None

router = APIRouter(tags=["system"])


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": get_version(app) if app else "unknown"}


@router.get("/api/config")
async def get_config_api():
    """Get WebUI extended configuration (API keys masked)."""
    return svc.get_config()


@router.put("/api/config")
async def update_config_api(request: Request):
    """Update WebUI extended configuration."""
    body = await request.json()
    svc.update_config(body)
    return {"status": "ok"}


@router.get("/api/update/check")
async def check_update():
    """Check if a newer version is available on GitHub."""
    return await svc.check_update()


@router.post("/api/update/apply")
async def apply_update():
    """Pull latest changes from GitHub and restart."""
    return StreamingResponse(
        svc.stream_update(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Model Switching Routes ──────────────────────────────────────────
# NOTE: Model endpoints grouped here.


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
