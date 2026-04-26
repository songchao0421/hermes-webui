"""
onboarding — 初始化引导路由

首次启动时检测环境状态并返回 JSON 供前端展示引导页。
也提供保存 API Key 的接口（通过 model_profiles.json 写入）。
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.ollama_service import check_ollama as _check_ollama, get_ollama_models_sync

logger = logging.getLogger("hermes_webui.onboarding")

router = APIRouter(tags=["onboarding"])


# ── Models ──────────────────────────────────────────────────────────────────


class OnboardingStatus(BaseModel):
    """初始化状态快照。"""
    ollama_running: bool = False
    ollama_models: list[str] = []
    has_deepseek_key: bool = False
    has_any_profile: bool = False
    completed: bool = False  # True = 无需引导


class SaveApiKeyRequest(BaseModel):
    provider: str  # "deepseek" | "openai" | "anthropic" 等
    api_key: str


# ── Helpers ─────────────────────────────────────────────────────────────────


def _check_api_key(provider: str = "deepseek") -> bool:
    """检查某个 provider 是否已配置 API Key。"""
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        providers = cfg.get("providers", {}) or {}
        if provider in providers:
            pk = providers[provider]
            if isinstance(pk, dict) and pk.get("api_key"):
                return True
        return False
    except Exception:
        return False


def _has_any_profile() -> bool:
    """检查是否有任何模型 profile 已配置。"""
    try:
        from services.model_switch import load_profiles
        data = load_profiles()
        return bool(data.get("profiles"))
    except Exception:
        return False


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("/api/onboarding/status")
async def get_onboarding_status() -> OnboardingStatus:
    """获取初始化状态，供前端引导页使用。"""
    ollama_running = _check_ollama()
    ollama_models = get_ollama_models_sync() if ollama_running else []
    has_deepseek_key = _check_api_key("deepseek")
    has_any_profile = _has_any_profile()

    # 如果 Ollama 已运行 + 已有 profile → 认为是完成状态
    completed = has_any_profile and (ollama_running or has_deepseek_key)

    return OnboardingStatus(
        ollama_running=ollama_running,
        ollama_models=ollama_models,
        has_deepseek_key=has_deepseek_key,
        has_any_profile=has_any_profile,
        completed=completed,
    )


@router.post("/api/onboarding/save-key")
async def save_api_key(req: SaveApiKeyRequest):
    """保存 API Key 到 Hermes config.yaml。"""
    config_path = Path.home() / ".hermes" / "config.yaml"
    if not config_path.exists():
        raise HTTPException(400, "Hermes config.yaml not found — 请先运行 hermes init")

    try:
        import yaml

        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}

        providers = cfg.setdefault("providers", {})
        provider_cfg = providers.setdefault(req.provider, {})
        if not isinstance(provider_cfg, dict):
            provider_cfg = {}
        provider_cfg["api_key"] = req.api_key
        providers[req.provider] = provider_cfg
        cfg["providers"] = providers

        with open(config_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

        logger.info("Saved API key for provider: %s", req.provider)
        return {"status": "ok", "provider": req.provider}

    except Exception as e:
        raise HTTPException(500, f"Failed to save API key: {e}")


@router.get("/api/onboarding/test-connection/{provider}")
async def test_connection(provider: str):
    """测试指定 provider 的连接（仅限本地不会触发扣费的 ping）。"""
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        providers = cfg.get("providers", {}) or {}
        pk = providers.get(provider, {})
        if isinstance(pk, dict) and pk.get("api_key"):
            return {"status": "ok", "message": f"{provider} API Key 已配置"}
        return {"status": "error", "message": f"{provider} 未配置 API Key"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/onboarding/dismiss")
async def dismiss_onboarding():
    """标记引导页已完成（创建 marker 文件）。"""
    marker = Path.home() / ".hermes" / "hermes-webui" / ".onboarding_done"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("")
    return {"status": "ok"}
