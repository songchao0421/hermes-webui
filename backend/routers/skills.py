"""
马鞍 (Ma'an) — Skills Router
Hermes skill management endpoints.
"""
import json
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from config import get_upload_dir

router = APIRouter(tags=["skills"])

# Module-level globals (injected by app.py)
_bridge = None
_load_webui_config = None
_save_webui_config = None


@router.get("/api/skills")
async def get_skills():
    """List all installed Hermes skills."""
    return {"skills": _bridge.get_skills()}


@router.post("/api/skills/import")
async def import_skill(file: UploadFile = File(...)):
    """Import a skill from a zip file."""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files are supported")

    temp_dir = get_upload_dir() / "temp_skill"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    zip_path = temp_dir / "skill.zip"
    with open(zip_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        skill_dir = None
        for item in temp_dir.iterdir():
            if item.is_dir():
                if (item / "SKILL.md").exists() or (item / "hermes_skill.json").exists():
                    skill_dir = item
                    break

        if not skill_dir:
            if (temp_dir / "SKILL.md").exists() or (temp_dir / "hermes_skill.json").exists():
                skill_dir = temp_dir
            else:
                raise HTTPException(status_code=400, detail="Invalid skill package: missing SKILL.md or hermes_skill.json")

        skill_id = skill_dir.name
        skill_name = skill_dir.name
        skill_desc = ""
        if (skill_dir / "hermes_skill.json").exists():
            with open(skill_dir / "hermes_skill.json", encoding="utf-8") as f:
                skill_data = json.load(f)
                skill_id = skill_data.get("id", skill_data.get("name", skill_id))
                skill_name = skill_data.get("name", skill_name)
                skill_desc = skill_data.get("description", "")
                print(f"[Import Skill] Found hermes_skill.json: id={skill_id}, name={skill_name}")

        target_dir = _bridge.skills_dir / skill_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(skill_dir, target_dir)
        shutil.rmtree(temp_dir)

        return {"status": "ok", "skill": skill_id, "name": skill_name}
    except HTTPException:
        raise
    except Exception as e:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")


@router.put("/api/skills/{skill_id}/toggle")
async def toggle_skill(skill_id: str, request: Request):
    """Enable or disable a skill (stores state in webui_config)."""
    body = await request.json()
    enabled = bool(body.get("enabled", True))
    cfg = _load_webui_config()
    cfg.setdefault("skill_states", {})[skill_id] = enabled
    _save_webui_config(cfg)
    return {"status": "ok", "skill_id": skill_id, "enabled": enabled}


@router.get("/api/skills/{skill_id}/config")
async def get_skill_config(skill_id: str):
    """Get persisted config for a skill."""
    cfg = _load_webui_config()
    return cfg.get("skill_configs", {}).get(skill_id, {})


@router.put("/api/skills/{skill_id}/config")
async def update_skill_config(skill_id: str, request: Request):
    """Save config for a skill."""
    body = await request.json()
    cfg = _load_webui_config()
    cfg.setdefault("skill_configs", {})[skill_id] = body
    _save_webui_config(cfg)
    return {"status": "ok"}


@router.get("/api/skills/{skill_id}/readme")
async def get_skill_readme(skill_id: str):
    """Return SKILL.md content for a skill."""
    skill_dir = _bridge.skills_dir / skill_id
    for fname in ("SKILL.md", "README.md"):
        fpath = skill_dir / fname
        if fpath.exists():
            return {"content": fpath.read_text(encoding="utf-8")}
    return {"content": ""}


@router.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    """Delete an installed skill."""
    skill_dir = _bridge.skills_dir / skill_id
    if not skill_dir.exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    shutil.rmtree(skill_dir)
    return {"status": "ok"}
