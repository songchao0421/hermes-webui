"""
Hermes WebUI — Persona Router (thin)
Delegates business logic to services/persona_service.py.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from models import PersonaUpdate
from services.persona_service import PersonaService

router = APIRouter(tags=["persona"])

# Injected by app.py lifespan
_service: PersonaService = None  # type: ignore[assignment]


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/api/persona")
async def get_persona():
    return _service.get_with_presets()


@router.put("/api/persona")
async def update_persona(body: PersonaUpdate):
    persona = _service.update(body)
    return {"status": "ok", "persona": persona}


@router.post("/api/persona/avatar")
async def upload_avatar(file: UploadFile = File(...), type: str = Form(default="agent")):
    filename = _service.upload_avatar(file, type)
    return {"status": "ok", "avatar": filename}


@router.get("/api/persona/avatar/{filename}")
async def serve_avatar(filename: str):
    filepath = _service.resolve_avatar_path(filename)
    if filepath is None:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(filepath)
