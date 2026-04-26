"""
Hermes WebUI — Persona Service
Agent personalization: name, avatar, theme management.
All persona data and business logic lives here.
"""

import copy
import json
import logging
from pathlib import Path

from fastapi import HTTPException, UploadFile

logger = logging.getLogger("hermes_webui.persona_service")

DEFAULT_PERSONA = {
    "agent_name": "My Agent",
    "user_display_name": "",
    "user_avatar": "",
    "avatar": "logo.png",
    "avatar_preset": "",
    "theme": {
        "accent": "#e8a849",
        "accent_dim": "#452b00",
        "preset": "amber",
    },
    "setup_complete": False,
}

THEME_PRESETS = {
    "amber":  {"accent": "#e8a849", "accent_dim": "#452b00"},
    "cyan":   {"accent": "#00daf3", "accent_dim": "#005b67"},
    "purple": {"accent": "#d0bcff", "accent_dim": "#571bc1"},
    "green":  {"accent": "#81c784", "accent_dim": "#2e7d32"},
    "rose":   {"accent": "#f48fb1", "accent_dim": "#c2185b"},
}

ALLOWED_AVATAR_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}

MAX_AVATAR_SIZE = 5 * 1024 * 1024


class PersonaService:
    def __init__(self, persona_dir: Path, persona_file: Path, avatar_dir: Path):
        self._persona_dir = persona_dir
        self._persona_file = persona_file
        self._avatar_dir = avatar_dir

    # ── Persona CRUD ─────────────────────────────────────────────────

    def load(self) -> dict:
        persona = copy.deepcopy(DEFAULT_PERSONA)
        if self._persona_file.exists():
            try:
                saved = json.loads(self._persona_file.read_text(encoding="utf-8"))
                for key, value in saved.items():
                    if isinstance(value, dict) and isinstance(persona.get(key), dict):
                        persona[key] = {**persona[key], **value}
                    else:
                        persona[key] = value
            except Exception:
                logger.warning("Failed to load persona from %s", self._persona_file)
        return persona

    def save(self, persona: dict) -> None:
        self._persona_dir.mkdir(parents=True, exist_ok=True)
        self._persona_file.write_text(
            json.dumps(persona, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_with_presets(self) -> dict:
        persona = self.load()
        persona["theme_presets"] = THEME_PRESETS
        return persona

    def update(self, body) -> dict:
        """Apply partial updates from a PersonaUpdate model."""
        persona = self.load()
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
        self.save(persona)
        return persona

    # ── Avatar ───────────────────────────────────────────────────────

    def upload_avatar(self, file: UploadFile, avatar_type: str = "agent") -> str:
        """Upload an avatar image. Returns the saved filename."""
        self._avatar_dir.mkdir(parents=True, exist_ok=True)

        if file.content_type not in ALLOWED_AVATAR_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported image format")

        ext = ALLOWED_AVATAR_TYPES[file.content_type]
        filename = f"{avatar_type}_avatar.{ext}" if avatar_type == "user" else f"avatar.{ext}"
        filepath = self._avatar_dir / filename

        content = file.file.read()
        if len(content) > MAX_AVATAR_SIZE:
            raise HTTPException(status_code=413, detail="Avatar file too large. Maximum size is 5 MB.")

        filepath.write_bytes(content)

        persona = self.load()
        if avatar_type == "user":
            persona["user_avatar"] = filename
        else:
            persona["avatar"] = filename
        self.save(persona)

        return filename

    def resolve_avatar_path(self, filename: str) -> Path | None:
        """Resolve an avatar filename to an actual file path, with security checks."""
        # Sanitize
        if "/" in filename or "\\" in filename or ".." in filename:
            return None

        # Check avatar dir
        avatar_path = (self._avatar_dir / filename).resolve()
        if avatar_path.exists() and str(avatar_path).startswith(str(self._avatar_dir.resolve())):
            return avatar_path

        # Check frontend dir
        frontend_dir = Path(__file__).parent.parent / "frontend"
        frontend_path = (frontend_dir / filename).resolve()
        if frontend_path.exists() and str(frontend_path).startswith(str(frontend_dir.resolve())):
            return frontend_path

        # Check project root
        project_root = Path(__file__).parent.parent
        root_path = (project_root / filename).resolve()
        if root_path.exists() and str(root_path).startswith(str(project_root.resolve())):
            return root_path

        return None
