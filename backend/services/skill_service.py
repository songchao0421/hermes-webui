"""
Skill Service — business logic for Hermes skill management.

Extracted from routers/skills.py. Receives _bridge via constructor injection.
"""

import json
import shutil
import zipfile
import logging
from pathlib import Path

from fastapi import HTTPException, UploadFile
from config import get_upload_dir

logger = logging.getLogger("hermes_webui.skill_service")


class SkillService:
    def __init__(self, bridge, load_webui_config_func, save_webui_config_func):
        self._bridge = bridge
        self._load_webui_config = load_webui_config_func
        self._save_webui_config = save_webui_config_func

    @property
    def skills_dir(self):
        return self._bridge.skills_dir

    # ── Skill APIs ─────────────────────────────────────────────────

    def get_skills(self):
        return self._bridge.get_skills()

    async def import_skill(self, file: UploadFile) -> dict:
        """Import a skill from a zip file."""
        if not file.filename.endswith(".zip"):
            raise HTTPException(status_code=400, detail="Only .zip files are supported")

        temp_dir = get_upload_dir() / "temp_skill"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        zip_path = temp_dir / "skill.zip"
        content = await file.read()
        zip_path.write_bytes(content)

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
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

            manifest = skill_dir / "hermes_skill.json"
            if manifest.exists():
                skill_data = json.loads(manifest.read_text(encoding="utf-8"))
                skill_id = skill_data.get("id", skill_data.get("name", skill_id))
                skill_name = skill_data.get("name", skill_name)
                skill_desc = skill_data.get("description", "")
                logger.info("Import skill: id=%s name=%s", skill_id, skill_name)

            target_dir = self.skills_dir / skill_id
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

    def toggle_skill(self, skill_id: str, enabled: bool) -> dict:
        """Enable or disable a skill."""
        cfg = self._load_webui_config()
        cfg.setdefault("skill_states", {})[skill_id] = enabled
        self._save_webui_config(cfg)
        return {"status": "ok", "skill_id": skill_id, "enabled": enabled}

    def get_skill_config(self, skill_id: str) -> dict:
        cfg = self._load_webui_config()
        return cfg.get("skill_configs", {}).get(skill_id, {})

    def update_skill_config(self, skill_id: str, body: dict) -> dict:
        cfg = self._load_webui_config()
        cfg.setdefault("skill_configs", {})[skill_id] = body
        self._save_webui_config(cfg)
        return {"status": "ok"}

    def get_skill_readme(self, skill_id: str) -> str:
        skill_dir = self.skills_dir / skill_id
        for fname in ("SKILL.md", "README.md"):
            fpath = skill_dir / fname
            if fpath.exists():
                return fpath.read_text(encoding="utf-8")
        return ""

    def delete_skill(self, skill_id: str) -> None:
        skill_dir = self.skills_dir / skill_id
        if not skill_dir.exists():
            raise HTTPException(status_code=404, detail="Skill not found")
        shutil.rmtree(skill_dir)
