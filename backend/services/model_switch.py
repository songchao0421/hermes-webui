"""
Hermes WebUI — Model Switch Service
=====================================
Manages model profiles and hot-switches the Hermes config.yaml model stanza.

Architecture:
  - model_profiles.json stores named profiles (remote/local models)
  - Switching writes the new model stanza to config.yaml
  - Switching triggers config.py reload_config() so next message picks up
  - Auto-discovers local Ollama models and can add them as ad-hoc profiles

Thread safety: file operations are short and atomic (write-then-rename).
"""

import json
import os
import re
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("hermes_webui.model_switch")

# ── File Paths ──────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".hermes"
PROFILES_FILE = CONFIG_DIR / "model_profiles.json"
CONFIG_YAML = CONFIG_DIR / "config.yaml"

# ── Ollama endpoints (auto-detect: Windows Ollama in WSL, then remote) ──
_OLLAMA_CANDIDATES = []
import socket as _socket
for _ip in ["172.18.224.1", "192.168.1.12", "localhost", "host.docker.internal"]:
    try:
        _sock = _socket.create_connection((_ip, 11434), timeout=1)
        _sock.close()
        _OLLAMA_CANDIDATES.append(f"http://{_ip}:11434")
    except Exception:
        pass
OLLAMA_BASE = _OLLAMA_CANDIDATES[0] if _OLLAMA_CANDIDATES else "http://192.168.1.12:11434"
OLLAMA_API = f"{OLLAMA_BASE}/v1"
OLLAMA_TAGS = f"{OLLAMA_BASE}/api/tags"

# ── Default Profiles ───────────────────────────────────────────────

DEFAULT_PROFILES = {
    "profiles": {
        "deepseek-chat": {
            "name": "DeepSeek Chat",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "type": "remote",
            "cost_tier": "paid",
        },
        "deepseek-reasoner": {
            "name": "DeepSeek Reasoner",
            "provider": "deepseek",
            "model": "deepseek-reasoner",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "type": "remote",
            "cost_tier": "paid",
        },
    },
    "current_profile": "deepseek-chat",
    "updated_at": None,
}

# ── Load / Save Profiles ───────────────────────────────────────────


def load_profiles() -> dict:
    """Load model profiles from JSON file. Returns full dict with 'profiles' key."""
    if PROFILES_FILE.exists():
        try:
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "profiles" in data:
                return data
        except Exception as e:
            logger.warning(f"Failed to load profiles: {e}")
    return dict(DEFAULT_PROFILES)


def save_profiles(data: dict):
    """Save model profiles to JSON file atomically."""
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROFILES_FILE.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(PROFILES_FILE)


# ── Read current model stanza from config.yaml ────────────────────


def _read_config_yaml() -> Optional[str]:
    """Read the entire config.yaml as text. Returns None if missing."""
    if not CONFIG_YAML.exists():
        return None
    try:
        return CONFIG_YAML.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read config.yaml: {e}")
        return None


def _write_config_yaml(content: str):
    """Write config.yaml atomically."""
    CONFIG_YAML.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_YAML.with_suffix(".yaml.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(CONFIG_YAML)


def _update_vision_config(model_name: str = "qwen3.6:27b-q4_K_M"):
    """Auto-update auxiliary.vision in config.yaml with the detected Ollama base_url.

    The vision config lives under `auxiliary.vision` in Hermes config.yaml.
    We update base_url and model to match the auto-detected Ollama endpoint,
    so the user never has to hardcode an IP address.
    """
    base_url = f"{OLLAMA_BASE}/v1"
    yaml_text = _read_config_yaml()
    if not yaml_text:
        return

    # Find the auxiliary.vision block boundaries and only replace inside it.
    # The block looks like:
    #     auxiliary:
    #       vision:
    #         provider: custom
    #         model: 'qwen3.6:27b-q4_K_M'
    #         base_url: 'http://...'
    #         ...
    #       web_extract:
    #       compression:
    #       ...
    #
    # All vision children are indented 4 spaces under "  vision:".
    # We target lines matching "^    model:" and "^    base_url:" that appear
    # right after "  vision:" — this is safe because only vision uses those
    # exact indentation levels for model/base_url under auxiliary.

    lines = yaml_text.split("\n")
    new_lines = []
    in_vision = False
    changed = False

    for line in lines:
        stripped = line.rstrip()
        # Detect entering vision block: "  vision:" under "auxiliary:"
        if re.match(r"^  vision:\s*$", stripped):
            in_vision = True
            new_lines.append(line)
            continue
        # Detect leaving vision block: next sibling under auxiliary (e.g. "  web_extract:")
        # or a top-level key (no leading space)
        if in_vision:
            if re.match(r"^  \S", stripped) or re.match(r"^\S", stripped):
                # We've left the vision block
                in_vision = False
                new_lines.append(line)
                continue
            else:
                # Still inside vision block; check for model or base_url
                m = re.match(r"^    (model|base_url):.*$", stripped)
                if m:
                    key = m.group(1)
                    if key == "model":
                        new_lines.append(f"    model: '{model_name}'")
                    else:
                        new_lines.append(f"    base_url: '{base_url}'")
                    changed = True
                    continue
                # Not a model/base_url line inside vision — keep as-is
                new_lines.append(line)
                continue

        new_lines.append(line)

    if changed:
        new_content = "\n".join(new_lines)
        _write_config_yaml(new_content)
        logger.info(f"Vision config auto-updated: model={model_name}, base_url={base_url}")
    else:
        logger.debug("Vision config unchanged or vision block not found")


def get_current_config() -> dict:
    """Get the current model configuration from config.yaml.

    Returns dict with keys: provider, model, base_url, type, api_key_env, api_key.
    Falls back to deepseek defaults if config.yaml is unreadable.
    """
    yaml_text = _read_config_yaml()
    if not yaml_text:
        return {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "type": "remote",
        }

    provider = _extract_yaml_value(yaml_text, "model", "provider")
    model = _extract_yaml_value(yaml_text, "model", "default")
    base_url = _extract_yaml_value(yaml_text, "model", "base_url")

    return {
        "provider": provider or "deepseek",
        "model": model or "deepseek-chat",
        "base_url": base_url or "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "type": "remote",
    }


def _extract_yaml_value(text: str, section: str, key: str) -> Optional[str]:
    """Extract a single YAML key value from a section.

    Handles:
      section:
        key: value
        key: 'value'
        key: "value"
    """
    pattern = rf"^{re.escape(section)}:\s*$"
    lines = text.split("\n")
    in_section = False
    for line in lines:
        stripped = line.rstrip()
        if not in_section:
            if re.match(pattern, stripped):
                in_section = True
            continue
        # Stop at next top-level key (no indent)
        if stripped and not stripped.startswith(" ") and not stripped.startswith("\t"):
            if ":" in stripped:
                break
        m = re.match(r"^\s+{re.escape(key)}:\s*(.*?)$", stripped)
        if m:
            val = m.group(1).strip().strip("'\"").strip()
            return val if val else None
    return None


# ── Switch Model (hot-switch config.yaml model stanza) ────────────


def switch_model(profile_id: str) -> dict:
    """Switch to a profile by ID.

    Steps:
      1. Load profile from model_profiles.json
      2. Read current config.yaml
      3. Replace the model: stanza with profile values
      4. Write back atomically
      5. Trigger config reload

    Returns dict with {success, profile, error?}
    """
    data = load_profiles()
    profiles = data.get("profiles", {})
    profile = profiles.get(profile_id)

    if not profile:
        return {"success": False, "error": f"Profile '{profile_id}' not found"}

    yaml_text = _read_config_yaml()
    if not yaml_text:
        return {"success": False, "error": "config.yaml not found"}

    # Build the new model stanza
    provider = profile.get("provider", "deepseek")
    model_name = profile.get("model", profile_id)
    base_url = profile.get("base_url", "https://api.deepseek.com/v1")
    ctx = profile.get("context_length", 131072)  # Default 128K for local models

    new_stanza = f"model:\n  base_url: {base_url}\n  default: {model_name}\n  provider: {provider}\n  context_length: {ctx}\n"

    # Replace the model: stanza at top level
    # Pattern: start of line, "model:" then everything up to next top-level key or EOF
    lines = yaml_text.split("\n")
    new_lines = []
    in_model = False
    replaced = False

    for line in lines:
        stripped = line.rstrip()
        if not in_model:
            if re.match(r"^model:\s*$", stripped):
                in_model = True
                continue
            new_lines.append(line)
        else:
            # Check if we've reached the next top-level key
            if stripped and not stripped.startswith(" ") and not stripped.startswith("\t"):
                if ":" in stripped:
                    # This is the next top-level key — insert new stanza before it
                    new_lines.append(new_stanza)
                    new_lines.append(line)
                    in_model = False
                    replaced = True
                    continue

        if not in_model:
            new_lines.append(line)

    # If model stanza was the last thing (no next key found)
    if in_model and not replaced:
        new_lines.append(new_stanza)
        replaced = True
        in_model = False

    # Filter out any blank trailing lines from the original model section digest
    new_content = "\n".join(new_lines)

    # Remove duplicates of the new stanza if somehow inserted twice
    if new_content.count("model:") > 1:
        # Fall back to regex replacement
        new_content = re.sub(
            r"^model:\n(?:  [^\n]+\n)*",
            new_stanza,
            yaml_text,
            count=1,
            flags=re.MULTILINE,
        )

    _write_config_yaml(new_content)

    # ── Auto-update vision stanza ──
    # Keep vision model and base_url in sync with Ollama auto-detection
    if profile.get("type") == "local":
        # For local models, ensure vision uses the same auto-detected Ollama
        _update_vision_config(model_name=model_name)
    # (For remote models, leave vision unchanged — user may still use local vision)

    # Update current_profile in profiles file
    data["current_profile"] = profile_id
    data["updated_at"] = _now_iso()
    save_profiles(data)

    # Trigger config reload in WebUI's config module
    _reload_webui_config()

    return {
        "success": True,
        "profile": {
            "id": profile_id,
            "name": profile.get("name", model_name),
            "provider": provider,
            "model": model_name,
            "type": profile.get("type", "remote"),
            "cost_tier": profile.get("cost_tier", "free"),
        },
    }


def _reload_webui_config():
    """Try to reload the WebUI config cache so next message picks up changes."""
    try:
        from config import reload_config
        reload_config()
        logger.info("WebUI config cache reloaded after model switch")
    except ImportError:
        pass  # Not running in WebUI context


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


# ── Discover Local Ollama Models ──────────────────────────────────


async def discover_ollama_models() -> List[dict]:
    """Query local Ollama (Windows) for available models.

    Returns list of profile dicts that don't already exist in profiles.
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(OLLAMA_TAGS)
            if resp.status_code != 200:
                logger.warning(f"Ollama tags API returned {resp.status_code}")
                return []

            remote_models = resp.json().get("models", [])
            data = load_profiles()
            existing = set(data.get("profiles", {}).keys())

            discovered = []
            for m in remote_models:
                name = m.get("name", "")
                if not name:
                    continue
                # Skip embeddings and non-chat models
                if ":embed" in name or "nomic-embed" in name:
                    continue
                profile_id = name.replace(":", "-").replace("/", "-")
                if profile_id in existing:
                    continue
                discovered.append({
                    "id": profile_id,
                    "name": f"{name} (Local)",
                    "provider": "custom",
                    "model": name,
                    "base_url": OLLAMA_API,
                    "api_key": "ollama",
                    "type": "local",
                    "cost_tier": "free",
                    "context_length": 131072,  # Ollama models: default 128K
                })

            return discovered
    except Exception as e:
        logger.warning(f"Ollama discovery failed: {e}")
        return []


def add_discovered_profiles(profiles: List[dict]) -> int:
    """Add discovered Ollama profiles to the profiles file. Returns count added."""
    data = load_profiles()
    existing = data.setdefault("profiles", {})
    count = 0
    for p in profiles:
        pid = p["id"]
        if pid not in existing:
            existing[pid] = {
                "name": p["name"],
                "provider": p["provider"],
                "model": p["model"],
                "base_url": p["base_url"],
                "api_key": p.get("api_key", "ollama"),
                "type": p.get("type", "local"),
                "cost_tier": p.get("cost_tier", "free"),
                "context_length": p.get("context_length", 131072),
            }
            count += 1
    if count > 0:
        save_profiles(data)
    return count


# ── Public API ─────────────────────────────────────────────────────


def list_profiles() -> List[dict]:
    """Get all available profiles with active state.

    Returns list of {id, name, provider, model, type, cost_tier, active}
    """
    data = load_profiles()
    current = data.get("current_profile", "")
    profiles = data.get("profiles", {})
    result = []
    for pid, p in profiles.items():
        result.append({
            "id": pid,
            "name": p.get("name", pid),
            "provider": p.get("provider", "deepseek"),
            "model": p.get("model", pid),
            "type": p.get("type", "remote"),
            "cost_tier": p.get("cost_tier", "free"),
            "active": pid == current,
        })
    return result


def get_active_profile() -> Optional[dict]:
    """Get the currently active profile. Returns None if none set."""
    data = load_profiles()
    current = data.get("current_profile", "")
    if not current:
        return None
    profiles = data.get("profiles", {})
    p = profiles.get(current)
    if not p:
        return None
    return {
        "id": current,
        "name": p.get("name", current),
        "provider": p.get("provider", "deepseek"),
        "model": p.get("model", current),
        "type": p.get("type", "remote"),
        "cost_tier": p.get("cost_tier", "free"),
        "active": True,
    }


# ── Module-init: auto-update vision config on startup ──
# This ensures the vision stanza in config.yaml always uses the correct
# Ollama base_url (auto-detected above) — no hardcoded IPs.
try:
    _update_vision_config()
except Exception:
    pass  # best-effort; config will be updated on first switch_model call
