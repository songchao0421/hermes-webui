"""
Unified Ollama Detection / Connection Service
==============================================
Single source of truth for detecting Ollama availability and fetching
model lists. Eliminates the 9-way duplication that previously existed
across config.py, model_switch.py, task_router.py, onboarding.py,
memories.py, and _hermes_sdk_bridge.py.

Detection strategy:
1. Try reading ~/.hermes/config.yaml for `model.base_url`
2. If that fails, try socket/TCP probes on known candidates
3. Fall back to http://localhost:11434
"""

import logging
import socket as _socket
from pathlib import Path
from typing import List, Optional

import httpx

logger = logging.getLogger("hermes_webui.ollama_service")

# ── Config Path ──────────────────────────────────────────────────────────
CONFIG_YAML = Path.home() / ".hermes" / "config.yaml"

# ── Well-known Ollama endpoints ─────────────────────────────────────────
def _get_wsl_gateway() -> Optional[str]:
    """Detect WSL2 gateway IP (Windows host) from default route."""
    try:
        import subprocess
        r = subprocess.run(
            ["ip", "route"],
            capture_output=True, text=True, timeout=3,
        )
        for line in r.stdout.splitlines():
            if line.startswith("default via "):
                parts = line.split()
                if len(parts) >= 3:
                    return parts[2]
    except Exception:
        pass
    return None


def _list_candidates() -> list[str]:
    """Assemble candidate hosts for Ollama probing."""
    hosts = ["localhost", "host.docker.internal"]
    gw = _get_wsl_gateway()
    if gw and gw not in hosts:
        hosts.insert(0, gw)  # WSL gateway (Windows host) first
    return hosts


_CANDIDATES = _list_candidates()


def _read_ollama_url_from_config() -> Optional[str]:
    """Try to read Ollama base_url from ~/.hermes/config.yaml.

    Checks under both ``model.base_url`` and ``auxiliary.vision.base_url`` /
    ``auxiliary.ollama.base_url`` for maximum compatibility.
    """
    if not CONFIG_YAML.exists():
        return None
    try:
        import yaml
        with open(CONFIG_YAML, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        # 1. Primary location: model.base_url (most common)
        base = (cfg.get("model") or {}).get("base_url", "")
        if base:
            raw = base.rstrip("/")
            if raw.endswith("/v1"):
                raw = raw[:-3]
            return raw

        # 2. Fallback: auxiliary.ollama.base_url
        aux = cfg.get("auxiliary") or {}
        if isinstance(aux, dict):
            ollama_cfg = aux.get("ollama") or {}
            base = ollama_cfg.get("base_url", "")
            if base:
                return base.rstrip("/")

        # 3. Fallback: auxiliary.vision.base_url (used for vision tasks)
        vision_cfg = aux.get("vision") or {}
        base = vision_cfg.get("base_url", "")
        if base:
            raw = base.rstrip("/")
            if raw.endswith("/v1"):
                raw = raw[:-3]
            return raw
    except Exception as exc:
        logger.debug("Could not read Ollama URL from config: %s", exc)
    return None


def get_ollama_candidates() -> List[str]:
    """Return all possible Ollama base URL candidates.

    The first element is the most likely (from config or localhost probe).
    """
    urls: List[str] = []

    # 1. Config-derived URL (most authoritative)
    cfg_url = _read_ollama_url_from_config()
    if cfg_url:
        urls.append(cfg_url)

    # 2. Candidates discovered via TCP probe
    for host in _CANDIDATES:
        url = f"http://{host}:11434"
        if url not in urls:
            urls.append(url)

    # 3. Absolute fallback
    if "http://localhost:11434" not in urls:
        urls.append("http://localhost:11434")

    return urls


def get_ollama_base_url() -> str:
    """Determine the best Ollama base URL to use.

    Priority:
      1. Config file (~/.hermes/config.yaml → model.base_url)
      2. TCP socket probe on known candidates
      3. http://localhost:11434 (unconditional fallback)

    Unlike ``get_ollama_candidates()`` this returns a *single* URL,
    preferring the one that is actually reachable when possible.
    """
    # 1. Config
    cfg_url = _read_ollama_url_from_config()
    if cfg_url:
        # Verify it responds (best-effort within timeout)
        try:
            r = httpx.get(f"{cfg_url}/api/tags", timeout=2)
            if r.status_code == 200:
                return cfg_url
        except Exception:
            pass

    # 2. Probe candidates
    for host in _CANDIDATES:
        try:
            sock = _socket.create_connection((host, 11434), timeout=1)
            sock.close()
            url = f"http://{host}:11434"
            logger.debug("Ollama detected at %s", url)
            return url
        except Exception:
            continue

    # 3. Fallback
    return "http://localhost:11434"


def check_ollama() -> bool:
    """Synchronous check if any Ollama instance is reachable.

    Uses httpx.get (replaces the old socket-only probe and urllib variants).
    """
    for url in get_ollama_candidates():
        try:
            r = httpx.get(f"{url}/api/tags", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            continue
    return False


async def check_ollama_async() -> bool:
    """Async check if any Ollama instance is reachable.

    Uses httpx.AsyncClient (replaces the old urllib variants).
    """
    async with httpx.AsyncClient(timeout=3) as client:
        for url in get_ollama_candidates():
            try:
                r = await client.get(f"{url}/api/tags")
                if r.status_code == 200:
                    return True
            except Exception:
                continue
    return False


async def get_ollama_models_async() -> List[str]:
    """Async fetch of pulled Ollama model names.

    Tries each candidate URL in order, returning model list from the first
    that responds successfully.

    Returns
    -------
    list[str]
        Model names like ``["llama3.2:3b", "qwen2.5:14b"]``.
        Empty list if Ollama is unreachable or has no models.
    """
    async with httpx.AsyncClient(timeout=5) as client:
        for url in get_ollama_candidates():
            try:
                r = await client.get(f"{url}/api/tags")
                if r.status_code == 200:
                    data = r.json()
                    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            except Exception:
                continue
    return []


def get_ollama_models_sync() -> List[str]:
    """Synchronous fetch of pulled Ollama model names.

    Returns
    -------
    list[str]
        Model names. Empty list if unreachable.
    """
    for url in get_ollama_candidates():
        try:
            r = httpx.get(f"{url}/api/tags", timeout=5)
            if r.status_code == 200:
                data = r.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            continue
    return []
