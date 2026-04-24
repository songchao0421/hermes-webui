"""
马鞍 Ma'an — Central Configuration Module
===========================================

Single source of truth for all paths and settings.
Priority chain for data dir:
  1. MAAN_HOME environment variable
  2. config/maan.yaml → data_dir field
  3. ~/.maan/ (auto-migrate from ~/.hermes-webui if it exists)

Environment auto-detection:
  - detect available tools (hermes, ollama, python)
  - detect OS / WSL2 / paths
  - provide interactive first-run setup
"""

import os
import sys
import json
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("hermes_webui.config")

# ── Project Root ──────────────────────────────────────────────────
# Resolve the actual project root (where backend/ lives)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Possible config file names (project ships with maan.yaml)
CONFIG_FILE_NAMES = ["maan.yaml", "hermes-webui.yaml"]
LEGACY_DATA_DIR_NAME = ".hermes-webui"
NEW_DATA_DIR_NAME = ".maan"

# ── Load Config File ──────────────────────────────────────────────

_config_cache: Optional[dict] = None


def _find_config_file() -> Optional[Path]:
    """Find config file: project config/ dir first, then user config dir."""
    # 1. Project-level config
    for name in CONFIG_FILE_NAMES:
        p = PROJECT_ROOT / "config" / name
        if p.exists():
            return p
    # 2. User data dir config
    data_dir = _resolve_data_dir()
    if data_dir:
        p = data_dir / "config.yaml"
        if p.exists():
            return p
    return None


def load_config() -> dict:
    """Load config from file, return empty dict if not found."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    cfg_path = _find_config_file()
    if cfg_path:
        try:
            import yaml
            with open(cfg_path, "r", encoding="utf-8") as f:
                _config_cache = yaml.safe_load(f) or {}
                return _config_cache
        except Exception as e:
            logger.warning(f"Failed to load config {cfg_path}: {e}")

    _config_cache = {}
    return _config_cache


def reload_config():
    """Force reload config (e.g. after user edits)."""
    global _config_cache
    _config_cache = None


# ── Data Directory ────────────────────────────────────────────────

_data_dir_cache: Optional[Path] = None


def _resolve_data_dir() -> Optional[Path]:
    """Resolve data directory without auto-creating or logging."""
    # 1. Environment variable takes highest priority
    env_home = os.environ.get("MAAN_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()

    # 2. Config file
    cfg = load_config()
    cfg_dir = cfg.get("data_dir") or (cfg.get("server") or {}).get("data_dir")
    if cfg_dir:
        return Path(cfg_dir).expanduser().resolve()

    return None


def get_data_dir() -> Path:
    """
    Get the data directory, auto-detecting and migrating as needed.

    Priority:
      1. MAAN_HOME env var
      2. config/maan.yaml → data_dir
      3. ~/.maan/ (migrate from ~/.hermes-webui if present)

    Returns a Path that always exists (creates if needed).
    """
    global _data_dir_cache
    if _data_dir_cache is not None:
        return _data_dir_cache

    # Check explicit override
    explicit = _resolve_data_dir()
    if explicit:
        _data_dir_cache = explicit
        _data_dir_cache.mkdir(parents=True, exist_ok=True)
        return _data_dir_cache

    # Check for legacy ~/.hermes-webui
    legacy = Path.home() / LEGACY_DATA_DIR_NAME
    new_dir = Path.home() / NEW_DATA_DIR_NAME

    if legacy.exists() and not new_dir.exists():
        # Auto-migrate: rename legacy -> new
        logger.info(f"Migrating {legacy} -> {new_dir}")
        legacy.rename(new_dir)

    if not new_dir.exists():
        new_dir.mkdir(parents=True, exist_ok=True)

    _data_dir_cache = new_dir
    return _data_dir_cache


# ── Derived Paths (computed from get_data_dir()) ──────────────────

def get_sessions_dir() -> Path:
    return get_data_dir() / "sessions"


def get_persona_dir() -> Path:
    return get_data_dir()


def get_persona_file() -> Path:
    return get_data_dir() / "persona.json"


def get_avatar_dir() -> Path:
    return get_data_dir() / "avatar"


def get_webui_config_file() -> Path:
    return get_data_dir() / "webui_config.json"


def get_auth_dir() -> Path:
    return get_data_dir() / "auth"


def get_auth_token_file() -> Path:
    return get_auth_dir() / "auth_token"


def get_upload_dir() -> Path:
    """Temp upload directory, configurable or default."""
    cfg = load_config()
    ud = (cfg.get("server") or {}).get("upload_dir")
    if ud:
        return Path(ud).expanduser().resolve()
    return get_data_dir() / "uploads"


def get_memory_snapshots_dir() -> Path:
    return get_data_dir() / "memory_snapshots"


# ── Environment Detection ─────────────────────────────────────────


def is_wsl() -> bool:
    """Detect if running inside WSL2."""
    if bool(os.environ.get("WSL_DISTRO_NAME")):
        return True
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version") as f:
                return "microsoft" in f.read().lower()
    except Exception:
        pass
    return False


def is_windows() -> bool:
    """Detect if running on native Windows (not WSL)."""
    return sys.platform == "win32" or sys.platform == "cygwin"


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux") and not is_wsl()


def detect_windows_home() -> Optional[Path]:
    """Detect Windows home directory when running in WSL2."""
    if not is_wsl():
        return None

    # Try USERPROFILE env (forwarded by wsl.exe)
    wp = os.environ.get("USERPROFILE")
    if wp:
        win_path = wp.replace("\\", "/")
        import re as _re
        m = _re.match(r"^([a-zA-Z]):(/.*)", win_path)
        if m:
            return Path(f"/mnt/{m.group(1).lower()}{m.group(2)}")

    # Scan /mnt/c/Users/
    users_dir = Path("/mnt/c/Users")
    if users_dir.exists():
        for user_dir in sorted(users_dir.iterdir()):
            name = user_dir.name
            if name not in ("Public", "Default", "All Users", "Default User"):
                return user_dir

    return None


# ── Tool Detection ────────────────────────────────────────────────


def find_hermes() -> Optional[str]:
    """Find the hermes CLI executable."""
    # 1. PATH
    cmd = shutil.which("hermes")
    if cmd:
        return cmd

    # 2. Common install locations
    candidates = [
        Path.home() / "hermes-agent" / "venv" / "bin" / "hermes",
        Path.home() / ".local" / "bin" / "hermes",
        Path.home() / ".venv" / "bin" / "hermes",
        Path("/usr/local/bin/hermes"),
    ]
    for p in candidates:
        if p.exists() and os.access(p, os.X_OK):
            return str(p)

    # 3. Windows paths (running on Windows natively)
    if is_windows():
        win_candidates = [
            Path.home() / ".hermes" / "hermes-agent" / "venv" / "Scripts" / "hermes.exe",
            Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python311" / "Scripts" / "hermes.exe",
        ]
        for p in win_candidates:
            if p.exists():
                return str(p)

    return None


def has_ollama() -> bool:
    """Check if Ollama is reachable."""
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_ollama_models() -> list:
    """Get list of pulled Ollama models."""
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def get_config_value(*keys: str, default=None) -> Any:
    """Safely drill into config dict. E.g. get_config_value('server', 'port', default=8080)"""
    cfg = load_config()
    val = cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
    return val if val is not None else default


# ── First-Run Setup ──────────────────────────────────────────────


def first_run_setup(interactive: bool = True, quiet: bool = False) -> dict:
    """
    Auto-detect environment and guide user through first setup.
    Returns a dict with setup results.

    Parameters
    ----------
    interactive : bool
        If True, ask user questions. If False, use auto-detection only.
    quiet : bool
        If True, suppress all output (for programmatic use).
    """
    result = {
        "data_dir": str(get_data_dir()),
        "wsl": is_wsl(),
        "hermes_found": False,
        "hermes_path": None,
        "ollama_found": False,
        "ollama_models": [],
        "python_version": sys.version,
        "setup_complete": False,
        "notes": [],
    }

    def tell(msg: str):
        if not quiet:
            print(f"  {msg}")

    # ── Data directory ──
    tell(f"[Config] Data dir: {get_data_dir()}")

    # ── Hermes detection ──
    hermes_path = find_hermes()
    if hermes_path:
        result["hermes_found"] = True
        result["hermes_path"] = hermes_path
        tell(f"[OK] Hermes CLI: {hermes_path}")
    else:
        result["notes"].append("Hermes CLI not found")
        if not quiet:
            tell("[...] Hermes CLI not found. Agent mode will be limited.")
            if interactive:
                ans = input("  Install Hermes? [Y/n] ").strip().lower()
                if ans in ("", "y", "yes"):
                    tell("  Installing hermes-agent via pip...")
                    try:
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", "hermes-agent"],
                            capture_output=True, timeout=120
                        )
                        if find_hermes():
                            result["hermes_found"] = True
                            result["hermes_path"] = find_hermes()
                            tell("[OK] Hermes installed!")
                        else:
                            tell("[!] Hermes install may have failed. Try: pip install hermes-agent")
                    except Exception as e:
                        tell(f"[!] Install error: {e}")
                else:
                    tell("[SKIP] Skipping Hermes install.")

    # ── Ollama detection ──
    if has_ollama():
        result["ollama_found"] = True
        models = get_ollama_models()
        result["ollama_models"] = models
        if models:
            tell(f"[OK] Ollama running, models: {', '.join(models[:5])}")
        else:
            tell("[OK] Ollama running (no models pulled yet)")
    else:
        result["notes"].append("Ollama not running")
        tell("[...] Ollama not detected.")
        if is_wsl():
            if interactive and not quiet:
                tell("  [WSL] Ollama runs on Windows, not inside WSL.")
                tell("  Download from https://ollama.com/download and install on Windows.")
                tell("  WSL will auto-detect Windows Ollama via localhost:11434.")
        elif is_linux():
            if interactive and not quiet:
                ans = input("  Install Ollama now? [Y/n] ").strip().lower()
                if ans in ("", "y", "yes"):
                    tell("  Run: curl -fsSL https://ollama.com/install.sh | sh")
                    tell("  Then re-launch Ma'an.")
        elif is_macos():
            if interactive and not quiet:
                tell("  Install Ollama: https://ollama.com/download  or  brew install ollama")
        elif is_windows():
            tell("  Install Ollama: https://ollama.com/download")

    # ── Python version check ──
    py_major = sys.version_info.major
    py_minor = sys.version_info.minor
    if py_major < 3 or (py_major == 3 and py_minor < 10):
        result["notes"].append(f"Python {py_major}.{py_minor} is below recommended 3.10+")
        tell(f"[!] Python {py_major}.{py_minor} detected — 3.10+ recommended")

    result["setup_complete"] = True
    return result


# ── Ensure Directories Exist ──────────────────────────────────────


def ensure_dirs():
    """Create all required directories at startup."""
    dirs = [
        get_data_dir(),
        get_sessions_dir(),
        get_avatar_dir(),
        get_auth_dir(),
        get_upload_dir(),
        get_memory_snapshots_dir(),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
