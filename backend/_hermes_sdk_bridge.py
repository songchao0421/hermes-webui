"""
Hermes WebUI — SDK Direct Bridge
==================================
Wraps the Hermes Agent AIAgent class for async WebUI consumption.
Replaces the old subprocess-based hermes_bridge.py.

Architecture:
  FastAPI (ASGI)  ←asyncio.Queue→  ThreadPoolExecutor  ←sync call→  AIAgent.run_conversation()

Each user message spawns a conversation turn in a thread. The AIAgent's
callbacks push events onto an asyncio.Queue, which the SSE endpoint reads.
Abort sets an asyncio.Event that the thread checks between iterations.
"""
import asyncio
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event types pushed to the SSE queue
# ---------------------------------------------------------------------------
EVT_TOKEN = "token"
EVT_TOOL_START = "tool_start"
EVT_TOOL_COMPLETE = "tool_complete"
EVT_THINKING = "thinking"
EVT_REASONING = "reasoning"
EVT_STATUS = "status"
EVT_DONE = "done"
EVT_ERROR = "error"

# ---------------------------------------------------------------------------
# Config loader — reads ~/.hermes/config.yaml the same way the CLI does
# ---------------------------------------------------------------------------
_CONF_DEFAULT = {"model": {"default": "deepseek-chat"}}


def _load_hermes_config() -> dict:
    """Load Hermes Agent config from ~/.hermes/config.yaml."""
    try:
        from hermes_cli.config import read_raw_config
        return read_raw_config()
    except ImportError:
        pass
    # Fallback: raw YAML read
    try:
        from pathlib import Path
        p = Path.home() / ".hermes" / "config.yaml"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def _get_model_config(cfg: dict) -> dict:
    """Return the effective model stanza from config.

    Priority:
      1. config["model"] dict (standard Hermes config structure)
      2. config["provider"] dict (legacy / WebUI config)
    """
    model_cfg = cfg.get("model") or cfg.get("provider") or {}
    if isinstance(model_cfg, str):
        return {}
    return model_cfg


# ---------------------------------------------------------------------------
# Running conversations — we keep a single thread pool
# ---------------------------------------------------------------------------
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hermes-sdk")


class HermesSDKBridge:
    """Manages one active AIAgent conversation per session.

    Also exposes Hermes environment helpers (skills, memory, config) consumed
    by routers that migrated from the old subprocess bridge.
    """

    def __init__(self):
        self._abort_event: Optional[asyncio.Event] = None
        self._active_task_id: Optional[str] = None

    # ── Hermes environment helpers (filesystem / config) ─────────────────

    @property
    def hermes_dir(self) -> Path:
        """~/.hermes/"""
        return Path.home() / ".hermes"

    @property
    def skills_dir(self) -> Path:
        """~/.hermes/skills/"""
        return self.hermes_dir / "skills"

    @property
    def memories_dir(self) -> Path:
        """~/.hermes/memories/ (also legacy ~/.hermes/ for SOUL.md)"""
        return self.hermes_dir / "memories"

    def _load_cfg(self) -> dict:
        return _load_hermes_config()

    def get_skills(self) -> list[dict]:
        """Scan ~/.hermes/skills/ and return a list of skill info dicts."""
        skills = []
        sd = self.skills_dir
        if not sd.is_dir():
            return skills
        for child in sorted(sd.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            info: dict[str, Any] = {"id": child.name, "name": child.name}
            # Read description from SKILL.md frontmatter
            skill_md = child / "SKILL.md"
            if skill_md.exists():
                text = skill_md.read_text(encoding="utf-8", errors="replace")
                for line in text.splitlines():
                    if line.startswith("description:"):
                        info["description"] = line[len("description:"):].strip().strip('"').strip("'")
                        break
            manifest = child / "hermes_skill.json"
            if manifest.exists():
                try:
                    meta = json.loads(manifest.read_text(encoding="utf-8"))
                    if "id" in meta:
                        info["id"] = meta["id"]
                    if "name" in meta:
                        info["name"] = meta["name"]
                    if "description" in meta:
                        info["description"] = meta.get("description", info.get("description", ""))
                except Exception:
                    pass
            skills.append(info)
        return skills

    @staticmethod
    def _memory_file_path(name: str) -> Optional[Path]:
        """Resolve SOUL.md / MEMORY.md / USER.md to its on-disk path."""
        name = name.strip()
        hermes = Path.home() / ".hermes"
        if name == "SOUL.md":
            return hermes / "SOUL.md"
        # MEMORY.md / USER.md live under .hermes/memories/
        memories = hermes / "memories"
        if name in ("MEMORY.md", "USER.md"):
            return memories / name
        return None

    def get_all_memories(self) -> dict:
        """Return content of all recognised memory files."""
        result: dict[str, str] = {}
        for fname in ("SOUL.md", "MEMORY.md", "USER.md"):
            fpath = self._memory_file_path(fname)
            if fpath and fpath.exists():
                result[fname] = fpath.read_text(encoding="utf-8", errors="replace")
            else:
                result[fname] = ""
        return result

    def read_memory(self, name: str) -> str:
        """Read a single memory file. Returns empty string if missing."""
        fpath = self._memory_file_path(name)
        if fpath and fpath.exists():
            return fpath.read_text(encoding="utf-8", errors="replace")
        return ""

    def write_memory(self, name: str, content: str) -> bool:
        """Write content to a memory file. Returns True on success."""
        fpath = self._memory_file_path(name)
        if not fpath:
            logger.warning("Unknown memory file: %s", name)
            return False
        fpath.parent.mkdir(parents=True, exist_ok=True)
        try:
            fpath.write_text(content, encoding="utf-8")
            return True
        except OSError as exc:
            logger.error("Failed to write memory %s: %s", name, exc)
            return False

    def get_ollama_url(self) -> str:
        """Return the configured Ollama base URL."""
        cfg = self._load_cfg()
        return cfg.get("model", {}).get("base_url", "http://localhost:11434")

    def get_default_model(self) -> str:
        """Return the configured default model name."""
        cfg = self._load_cfg()
        return cfg.get("model", {}).get("default", "")

    # ── Public API (conversation) ───────────────────────────────────────

    def abort(self):
        """Signal the running conversation to stop."""
        if self._abort_event and not self._abort_event.is_set():
            self._abort_event.set()
            logger.info("Abort signalled for task %s", self._active_task_id)

    async def run_conversation(
        self,
        user_message: str,
        system_message: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
        session_id: Optional[str] = None,
        file_paths: Optional[list[str]] = None,
    ) -> AsyncGenerator[dict, None]:
        """Run one conversation turn, yielding events as an async generator.

        Each yielded dict has at least a ``type`` key.  The caller is
        expected to serialise and stream these as SSE events.

        If *file_paths* are provided, each file's content is read and
        prepended to the *user_message* so the Agent receives it as
        context (equivalent to Hermes CLI's ``-a`` flag).
        """
        loop = asyncio.get_event_loop()
        self._abort_event = asyncio.Event()
        self._active_task_id = session_id or str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        abort = self._abort_event

        # Helper to put items thread-safely from a worker thread
        def _safe_put(item: dict):
            queue.put_nowait(item)

        # Load config
        hermes_cfg = _load_hermes_config()
        model_cfg = _get_model_config(hermes_cfg)

        agent_kwargs = {
            "model": model_cfg.get("default", ""),
            "base_url": model_cfg.get("base_url", ""),
            "provider": model_cfg.get("provider", ""),
            "api_key": model_cfg.get("api_key", ""),
            "session_id": self._active_task_id,
            "quiet_mode": True,  # suppress CLI chatter
            "verbose_logging": False,
            "stream_delta_callback": lambda d: _safe_put({
                "type": EVT_TOKEN, "content": d,
            }),
            "tool_start_callback": lambda tid, name, args: _safe_put({
                "type": EVT_TOOL_START, "id": tid, "name": name, "args": args,
            }),
            "tool_complete_callback": lambda tid, name, args, result: _safe_put({
                "type": EVT_TOOL_COMPLETE, "id": tid, "name": name,
                "result": str(result)[:2000],  # keep payloads bounded
            }),
            "thinking_callback": lambda text: _safe_put({
                "type": EVT_THINKING, "content": text,
            }),
            "reasoning_callback": lambda text: _safe_put({
                "type": EVT_REASONING, "content": text,
            }),
            "status_callback": lambda msg: _safe_put({
                "type": EVT_STATUS, "message": msg,
            }),
            "skip_context_files": False,
            "skip_memory": False,
            "persist_session": True,
            "max_tokens": model_cfg.get("max_tokens", 8192),
        }

        # Run in thread
        start = time.monotonic()
        thread_fut = asyncio.ensure_future(
            loop.run_in_executor(
                None, _run_agent_in_thread,
                agent_kwargs,
                user_message,
                system_message,
                conversation_history,
                abort,
                queue,
                file_paths or [],
            )
        )

        # Yield events from queue until done
        while True:
            get_task = asyncio.ensure_future(queue.get())
            abort_task = asyncio.ensure_future(self._wait_abort(abort))

            done_set, pending = await asyncio.wait(
                [get_task, abort_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if abort_task in done_set and abort_task.result():
                # Abort requested — cancel the thread task
                # AIAgent polls self._abort_event internally via self._stream_callback
                # But we also need to cancel the future
                for t in pending:
                    t.cancel()
                yield {"type": EVT_DONE, "aborted": True, "latency_ms": int((time.monotonic() - start) * 1000)}
                return

            # Cancel abort watcher going forward
            for t in pending:
                t.cancel()

            event = get_task.result()
            if event is _DONE_SENTINEL:
                break

            yield event

        # Final done event with timing
        latency = int((time.monotonic() - start) * 1000)
        yield {"type": EVT_DONE, "aborted": False, "latency_ms": latency}

        # Surface any thread exception
        exc = thread_fut.exception()
        if exc:
            logger.error("Agent thread raised: %s", exc)
            yield {"type": EVT_ERROR, "message": str(exc)}

        self._abort_event = None
        self._active_task_id = None

    # ── Internals ───────────────────────────────────────────────────────

    @staticmethod
    async def _wait_abort(abort: asyncio.Event) -> bool:
        """Wait for abort signal.  Returns True if aborted."""
        while not abort.is_set():
            await asyncio.sleep(0.1)
        return True


# ---------------------------------------------------------------------------
# Thread-bound helper
# ---------------------------------------------------------------------------
def _put_nowait(queue: asyncio.Queue, item: dict):
    """Thread-safe put to asyncio queue (called from agent callbacks)."""
    try:
        queue.put_nowait(item)
    except Exception:
        pass  # Queue full / cancelled — best-effort


_DONE_SENTINEL = object()


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


def _run_agent_in_thread(
    agent_kwargs: dict,
    user_message: str,
    system_message: Optional[str],
    conversation_history: Optional[list],
    abort_event: asyncio.Event,
    queue: asyncio.Queue,
    file_paths: list[str],
):
    """Execute AIAgent.run_conversation in a thread and signal completion.

    If *file_paths* are non-empty, each file is processed:
    - Image files → sent to Ollama llava:7b (via OpenAI-compatible endpoint),
      textual description prepended to user_message (works with ANY text-only
      model).  The file path is also included so the Agent can re-examine the
      image later with ``vision_analyze``.
    - Text files  → inline code block prepended.

    The Agent never sees raw base64 — only enriched text descriptions.
    """
    import base64
    from pathlib import Path

    try:
        # Ensure Hermes Agent modules are importable
        import sys
        agent_home = Path.home() / ".hermes" / "hermes-agent"
        if str(agent_home) not in sys.path:
            sys.path.insert(0, str(agent_home))

        from run_agent import AIAgent

        agent = AIAgent(**agent_kwargs)

        # ── Process attached files ────────────────────────────────────
        # Image files → analyze via vision_analyze_tool (Gemini Flash)
        #   and prepend textual description to user_message.
        #   Runs AFTER AIAgent init so Hermes provider config is loaded.
        # Text files → inline code block prepended.
        if file_paths:
            enriched_parts = []
            text_blocks = []
            vision_paths = []
            for fp in file_paths:
                fpath = Path(fp)
                if not fpath.is_file():
                    continue
                ext = fpath.suffix.lower()
                is_image = ext in _IMAGE_EXTENSIONS
                try:
                    if is_image:
                        vision_paths.append(fpath)
                    else:
                        text = fpath.read_text(encoding="utf-8", errors="replace")
                        text_blocks.append(f"File: {fpath.name}\n```\n{text}\n```")
                except Exception as exc:
                    logger.warning("Could not process attached file %s: %s", fp, exc)

            # ── Analyze images via Ollama vision model (single pass) ──
            # Uses minicpm-v:8b-2.6 (fast, 7.6B) configured in config.yaml vision section.
            # Chinese OCR + scene understanding in ONE call — no separate easyocr needed.
            if vision_paths:
                try:
                    from openai import OpenAI as _vision_openai

                    # Read vision config from ~/.hermes/config.yaml
                    _cfg = _load_hermes_config()
                    _aux = _cfg.get("auxiliary", {}) if isinstance(_cfg, dict) else {}
                    _vis = _aux.get("vision", {}) if isinstance(_aux, dict) else {}
                    _vision_base = _vis.get("base_url", "")  # must be configured in ~/.hermes/config.yaml
                    _vision_model = _vis.get("model", "qwen3.6:27b-q4_K_M")
                    _vision_key = _vis.get("api_key", "ollama")

                    _vision_client = _vision_openai(
                        api_key=_vision_key,
                        base_url=_vision_base,
                    )
                except Exception as exc:
                    logger.warning("Cannot init Gemini vision client: %s", exc)
                    _vision_client = None

                if _vision_client:
                    analysis_prompt = (
                        "先识别图中所有文字并逐行列出（OCR优先），然后简单描述这是什么场景。"
                    )
                    for img_path in vision_paths:
                        size_kb = img_path.stat().st_size // 1024
                        logger.info("Analyzing attached image %s (%dKB) via minicpm-v...", img_path.name, size_kb)
                        try:
                            import base64 as _b64
                            raw = img_path.read_bytes()
                            b64_data = _b64.b64encode(raw).decode("ascii")
                            ext = img_path.suffix.lower()
                            mime = "image/png" if ext == ".png" else "image/jpeg"
                            data_url = f"data:{mime};base64,{b64_data}"

                            resp = _vision_client.chat.completions.create(
                                model=_vision_model,
                                messages=[{
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": analysis_prompt},
                                        {"type": "image_url", "image_url": {"url": data_url}},
                                    ],
                                }],
                                max_tokens=2048,
                            )
                            description = resp.choices[0].message.content or ""
                            enriched_parts.append(
                                f"[用户上传了图片: {img_path.name}\n"
                                f"图片分析结果（OCR+场景描述）:\n{description}\n"
                                f"——如需更详细查看请用 vision_analyze 工具, image_url: {img_path}]"
                            )
                        except Exception as viz_err:
                            logger.warning("Image analysis failed for %s: %s", img_path.name, viz_err)
                            enriched_parts.append(
                                f"[用户上传了图片 ({img_path.name})，但分析失败: {viz_err}. "
                                f"可尝试 vision_analyze 工具查看, image_url: {img_path}]"
                            )
            prefix_parts = []
            if enriched_parts:
                prefix_parts.extend(enriched_parts)
            if text_blocks:
                prefix_parts.append("Attached files:\n\n" + "\n\n".join(text_blocks))
            if prefix_parts:
                user_message = "\n\n".join(prefix_parts) + "\n\n" + user_message

        # Inject abort check into stream_delta_callback so the agent
        # can bail out early when abort is requested
        original_delta = agent_kwargs.get("stream_delta_callback")
        if original_delta:

            def abort_aware_delta(content):
                if abort_event.is_set():
                    raise InterruptedError("Aborted by user")
                original_delta(content)

            agent._stream_callback = abort_aware_delta

        agent.run_conversation(
            user_message=user_message,
            system_message=system_message,
            conversation_history=conversation_history or [],
            # No stream_callback here — callbacks are set via __init__
        )
    except InterruptedError:
        # Expected — user aborted
        logger.info("Agent conversation aborted by user")
    except Exception as exc:
        logger.exception("Agent thread error")
        try:
            queue.put_nowait({"type": EVT_ERROR, "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            queue.put_nowait(_DONE_SENTINEL)
        except Exception:
            pass



