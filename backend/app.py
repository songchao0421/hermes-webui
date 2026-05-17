"""
Hermes WebUI - Backend Server
WebUI for Hermes Agent — graphical cockpit for the Hermes CLI.
Architecture: FastAPI assembly with SDK-direct agent bridge.
"""
import os, sys, logging, asyncio
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure backend/ is on sys.path for -m and direct script execution
_backend_dir = str(Path(__file__).resolve().parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from auth import require_auth, is_auth_enabled, check_token_file_permissions
from config import load_config, get_upload_dir, ensure_dirs, PROJECT_ROOT, get_sessions_dir, get_memory_snapshots_dir
from ratelimit import RateLimitExceeded, rate_limit_exceeded_handler
from services.static_files import NoCacheStaticFiles
from services.session_manager import (
    conversations, current_session_id, save_session, load_all_sessions,
    load_session as load_session_fn,
    _evict_old_sessions,
    get_sessions_for_user,
    get_owner_of_session,
    set_session_owner,
    remove_session_owner,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Runtime globals (set by CLI flags, consumed by routers) ───────
WSL_MODE = False
UPLOAD_TMP = get_upload_dir()
config = load_config()

# ── CLI Argument Parsing ──────────────────────────────────────────
import argparse
def parse_args():
    parser = argparse.ArgumentParser(description="Hermes WebUI")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind")
    parser.add_argument("--no-auth", action="store_true", help="Disable auth")
    parser.add_argument("--wsl-mode", action="store_true", help="Enable WSL mode")
    return parser.parse_args()

_args = None

# ── Lifespan ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load sessions. Shutdown: persist sessions."""
    ensure_dirs(); UPLOAD_TMP.mkdir(parents=True, exist_ok=True)
    load_all_sessions()

    # ── Token file permission check ──
    if is_auth_enabled():
        perm_info = check_token_file_permissions()
        if not perm_info["secure"]:
            for w in perm_info["warnings"]:
                logger.warning("[AUTH] %s", w)

    # ── Inject globals into routers ──
    import routers.system as _sys
    _sys.app = app

    import routers.agent as _agent
    _agent._conversations = conversations
    _agent._current_session_id = current_session_id
    _agent._save_session = save_session
    _agent._WSL_MODE = WSL_MODE

    import routers.memories as _mem
    _mem._bridge = _agent._bridge  # share the same SDK bridge instance
    _mem._current_session_id = current_session_id
    _mem._conversations = conversations
    _mem._get_memory_snapshots_dir = get_memory_snapshots_dir
    _mem._load_session = load_session_fn

    import routers.sessions as _sess
    _sess._conversations = conversations
    _sess._current_session_id = current_session_id
    _sess._SESSIONS_DIR = get_sessions_dir()
    _sess._load_session = load_session_fn
    _sess._evict_old_sessions = _evict_old_sessions
    _sess.set_session_owner = set_session_owner
    _sess.get_owner_of_session = get_owner_of_session
    _sess.remove_session_owner = remove_session_owner

    from services.skill_service import SkillService
    from services.webui_config import load_webui_config, save_webui_config
    import routers.skills as _sk
    import routers.agent as _agent_bridge
    _sk._service = SkillService(_agent_bridge._bridge, load_webui_config, save_webui_config)

    # ── Inject persona paths ──
    from services.persona_service import PersonaService
    from config import get_persona_dir, get_persona_file, get_avatar_dir
    import routers.persona as _pa
    _pa._service = PersonaService(
        persona_dir=get_persona_dir(),
        persona_file=get_persona_file(),
        avatar_dir=get_avatar_dir(),
    )

    # ── Initialize Model Switch Service ──
    import services.model_switch as _ms
    import routers.system as _sys
    _sys.model_switch = _ms

    # ── Inject model_switch into agent router for task routing ──
    import routers.agent as _agent_router
    _agent_router._model_switch = _ms

    # ── Banner ──
    total_sessions = sum(len(v) for v in conversations.values())
    total_users = len(conversations)
    logger.info("=" * 60)
    logger.info("  Hermes WebUI — Agent Console v2.1")
    logger.info("=" * 60)
    logger.info("  Users     : %d", total_users)
    logger.info("  Sessions  : %d loaded", total_sessions)
    logger.info("  Auth      : %s", "disabled" if not is_auth_enabled() else "enabled")
    logger.info("=" * 60)

    yield
    logger.info("Shutting down — saving sessions...")
    for uid, sessions in conversations.items():
        for sid, msgs in sessions.items():
            save_session(sid, msgs, owner=uid)

# ── FastAPI App ───────────────────────────────────────────────────
app = FastAPI(
    title="Hermes WebUI",
    description="Graphical cockpit for Hermes Agent",
    version="2.0.0",
    lifespan=lifespan,
    dependencies=[Depends(require_auth)],
)

app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS — 白名单：本地 + 内网
_origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://192.168.1.20",
    "https://192.168.1.20",
]
env_origins = os.environ.get("HERMES_CORS_ORIGINS", "")
if env_origins:
    _origins.extend(o.strip() for o in env_origins.split(",") if o.strip())
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])

# ── API Routes ──────────────────────────────────────────────────
from routers.persona import router as persona_router
from routers.system import router as system_router
from routers.agent import router as agent_router
from routers.memories import router as memories_router
from routers.sessions import router as sessions_router
from routers.skills import router as skills_router
from routers.onboarding import router as onboarding_router
from routers.files import router as files_router
from routers.auth import router as auth_router
from routers.admin import router as admin_router
from ratelimit import limit_10_per_minute

app.include_router(persona_router)
app.include_router(system_router)
app.include_router(memories_router)
app.include_router(skills_router)
app.include_router(sessions_router)
app.include_router(agent_router)
app.include_router(onboarding_router)
app.include_router(files_router)
app.include_router(auth_router)
app.include_router(admin_router)

# ── Rate-limit late-binding ──
memories_router.routes[-2].dependencies = [Depends(limit_10_per_minute)]

# ── Static Files ────────────────────────────────────────────────
frontend_dir = PROJECT_ROOT / "frontend"
if (frontend_dir / "assets").exists():
    app.mount("/assets", NoCacheStaticFiles(directory=str(frontend_dir / "assets")), name="assets")

# ── SPA fallback ────────────────────────────────────────────────
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = (frontend_dir / full_path).resolve()
    if file_path.is_file() and str(file_path).startswith(str(frontend_dir.resolve())):
        return FileResponse(file_path)
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"error": "Frontend not found"}, status_code=404)

# ── Entry Point ─────────────────────────────────────────────────
if __name__ == "__main__":
    from auth import set_auth_enabled
    _args = parse_args()
    if _args.wsl_mode:
        WSL_MODE = True
    set_auth_enabled(not _args.no_auth)
    uvicorn.run("app:app", host=_args.host, port=_args.port, reload=False)
