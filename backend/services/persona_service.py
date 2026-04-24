"""
马鞍 (Ma'an) — Persona Service
Agent personalization: name, avatar, theme management.
All persona data and business logic lives here.
"""
import copy
import json
from pathlib import Path

# ── Injected by app.py ────────────────────────────────────────────
PERSONA_DIR: Path | None = None
PERSONA_FILE: Path | None = None
AVATAR_DIR: Path | None = None

DEFAULT_PERSONA = {
    "agent_name": "My Agent",
    "user_display_name": "",
    "user_avatar": "",
    "avatar": "logo.png",        # Default avatar: project logo
    "avatar_preset": "",         # robot | face | bolt - used when no custom avatar
    "theme": {
        "accent": "#e8a849",      # Primary accent color (amber)
        "accent_dim": "#452b00",  # Darker accent for contrast
        "preset": "amber",        # cyan | purple | green | amber | rose | custom
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


def load_persona() -> dict:
    """Load user's agent personalization from disk."""
    persona = copy.deepcopy(DEFAULT_PERSONA)
    if PERSONA_FILE and PERSONA_FILE.exists():
        try:
            with open(PERSONA_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for key, value in saved.items():
                    if isinstance(value, dict) and isinstance(persona.get(key), dict):
                        persona[key] = {**persona[key], **value}
                    else:
                        persona[key] = value
        except Exception:
            pass
    return persona


def save_persona(persona: dict):
    """Save personalization to disk."""
    if PERSONA_DIR is None:
        return
    PERSONA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PERSONA_FILE, "w", encoding="utf-8") as f:
        json.dump(persona, f, ensure_ascii=False, indent=2)
