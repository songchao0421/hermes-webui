"""
Hermes WebUI — Skills Router (thin)

Delegates business logic to services/skill_service.py.
"""

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from services.skill_service import SkillService

router = APIRouter(tags=["skills"])

# Injected by app.py lifespan
_service: SkillService = None  # type: ignore[assignment]


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/api/skills")
async def get_skills():
    return {"skills": _service.get_skills()}


@router.post("/api/skills/import")
async def import_skill(file: UploadFile = File(...)):
    return await _service.import_skill(file)


@router.put("/api/skills/{skill_id}/toggle")
async def toggle_skill(skill_id: str, request: Request):
    body = await request.json()
    return _service.toggle_skill(skill_id, bool(body.get("enabled", True)))


@router.get("/api/skills/{skill_id}/config")
async def get_skill_config(skill_id: str):
    return _service.get_skill_config(skill_id)


@router.put("/api/skills/{skill_id}/config")
async def update_skill_config(skill_id: str, request: Request):
    body = await request.json()
    return _service.update_skill_config(skill_id, body)


@router.get("/api/skills/{skill_id}/readme")
async def get_skill_readme(skill_id: str):
    content = _service.get_skill_readme(skill_id)
    return {"content": content}


@router.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    _service.delete_skill(skill_id)
    return {"status": "ok"}
