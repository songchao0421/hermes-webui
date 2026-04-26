"""
WebUI Config — routing rules, API key providers, and budget tracking.

Owns:
  - WEBUI_CONFIG_FILE: Path

Provides:
  - load_webui_config() -> dict
  - save_webui_config(cfg)
"""

import json
import copy
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Config File Path ─────────────────────────────────────────────
from config import HERMES_HOME_DIR

CONFIG_DIR = HERMES_HOME_DIR
WEBUI_CONFIG_FILE = CONFIG_DIR / "webui_config.json"

# ── Default Config ───────────────────────────────────────────────

DEFAULT_CONFIG = {
    "routing": {
        "mode": "auto",
        "local": {"url": "http://localhost:11434", "model": ""},
        "api": {"providers": [], "active_provider": ""},
        "rules": {
            "code_threshold": True,
            "length_threshold": 500,
            "has_attachment": "api",
            "agent_mode": "hermes",
        },
        "monthly_budget_usd": 5.0,
        "monthly_used_usd": 0.0,
    }
}


# ── Load / Save ──────────────────────────────────────────────────

def load_webui_config() -> dict:
    """Load WebUI extended config (API keys, routing rules)."""
    if WEBUI_CONFIG_FILE.exists():
        try:
            with open(WEBUI_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_webui_config(cfg: dict):
    """Save WebUI extended config."""
    WEBUI_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WEBUI_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── Helpers ──────────────────────────────────────────────────────

def mask_api_keys(cfg: dict) -> dict:
    """Return a deep-copied config with API keys masked for security."""
    safe = copy.deepcopy(cfg)
    for p in safe.get("routing", {}).get("api", {}).get("providers", []):
        key = p.get("key", "")
        p["key"] = key[:4] + "****" + key[-4:] if len(key) > 8 else ("****" if key else "")
    return safe
