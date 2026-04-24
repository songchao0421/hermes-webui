"""
马鞍 (Ma'an) — Persona Router
Agent personalization: name, avatar, theme management.
"""
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from models import PersonaUpdate
from services.persona_service import (
    load_persona, save_persona, PERSONA_DIR, PERSONA_FILE,
    AVATAR_DIR, THEME_PRESETS, DEFAULT_PERSONA,
)

router = APIRouter(tags=["persona"])


@router.get("/api/persona")
async def get_persona():
    persona = load_persona()
    persona["theme_presets"] = THEME_PRESETS
    return persona


@router.put("/api/persona")
async def update_persona(body: PersonaUpdate):
    persona = load_persona()
    updates = body.model_dump(exclude_none=True, exclude={"theme"})
    for key, value in updates.items():
        persona[key] = value
    if body.theme:
        theme = body.theme
        preset = theme.preset or ""
        if preset in THEME_PRESETS:
            persona["theme"] = {**THEME_PRESETS[preset], "preset": preset}
        elif preset == "custom" and theme.accent:
            persona["theme"] = {
                "accent": theme.accent,
                "accent_dim": theme.accent_dim or theme.accent,
                "preset": "custom",
            }
    save_persona(persona)
    return {"status": "ok", "persona": persona}


@router.post("/api/persona/avatar")
async def upload_avatar(file: UploadFile = File(...), type: str = Form(default="agent")):
    if AVATAR_DIR is None:
        raise HTTPException(status_code=500, detail="Avatar directory not configured")
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    ALLOWED_TYPES = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image format")
    ext = ALLOWED_TYPES[file.content_type]
    filename = f"{type}_avatar.{ext}" if type == "user" else f"avatar.{ext}"
    filepath = AVATAR_DIR / filename
    MAX_AVATAR_SIZE = 5 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=413, detail="Avatar file too large. Maximum size is 5 MB.")
    with open(filepath, "wb") as f:
        f.write(content)
    persona = load_persona()
    if type == "user":
        persona["user_avatar"] = filename
    else:
        persona["avatar"] = filename
    save_persona(persona)
    return {"status": "ok", "avatar": filename}


@router.get("/api/persona/avatar/{filename}")
async def serve_avatar(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if AVATAR_DIR:
        filepath = (AVATAR_DIR / filename).resolve()
        if not str(filepath).startswith(str(AVATAR_DIR.resolve())):
            raise HTTPException(status_code=400, detail="Invalid filename")
        if filepath.exists():
            return FileResponse(filepath)
    frontend_dir = Path(__file__).parent.parent / "frontend"
    frontend_file = (frontend_dir / filename).resolve()
    if frontend_file.exists() and str(frontend_file).startswith(str(frontend_dir.resolve())):
        return FileResponse(frontend_file)
    project_root = Path(__file__).parent.parent
    root_file = (project_root / filename).resolve()
    if root_file.exists() and str(root_file).startswith(str(project_root.resolve())):
        return FileResponse(root_file)
    raise HTTPException(status_code=404, detail="Avatar not found")
