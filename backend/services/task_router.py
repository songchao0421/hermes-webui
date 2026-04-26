"""
Hermes WebUI — Intelligent Task Router
========================================
Automatically selects the optimal model for each user request
based on task complexity, token cost estimate, and historical corrections.

Architecture:
  - Analyzes user message: length, keywords, complexity signals
  - Scores on a 0-100 scale (0 = trivial, 100 = needs frontier model)
  - Routes to local (free) or remote (paid) model accordingly
  - Learns from user corrections via "re-route" feedback
  - Exposes LED status for frontend indicator

Integration:
  - Called by agent router BEFORE sending message to model
  - Can auto-switch model if routing decision differs from current
  - User can override via explicit "用DeepSeek" / "本地跑" in message
"""

import re
import logging
from typing import Optional, Dict, Any, List, Tuple

from services.correction_store import (
    record_correction,
    score_message,
)
from services.ollama_service import check_ollama as _check_ollama

logger = logging.getLogger("hermes_webui.task_router")

# ── Complexity Keywords ──────────────────────────────────────

# HIGH complexity: needs remote / frontier model
_HIGH_KEYWORDS = [
    # Architecture & design
    r"架构", r"设计", r"规划", r"方案", r"重构", r"整体",
    r"analyze", r"architecture", r"design.*pattern", r"refactor",
    r"复杂.*bug", r"性能.*优化", r"安全.*审计",
    # Multi-step reasoning
    r"分析.*影响", r"方案对比", r"拆解", r"逐步.*实现",
    r"trade.?off", r"pros.*cons", r"复杂度",
    # Hardcoded path audit / project state assessment
    r"hardcoded", r"审计", r"all.*files", r"整个项目",
    # Long code generation
    r"生成.*完整", r"编写.*模块", r"实现.*功能.*(详细|完整)",
    r"create.*full", r"implement.*complete",
    # Debugging
    r"为什么.*(不|没|失败|报错|error)", r"fix.*bug", r"debug",
    r"traceback", r"crash", r"崩溃", r"异常", r"error\b", r"bug\b",
]

# LOW complexity: can use local model
_LOW_KEYWORDS = [
    # File ops
    r"复制", r"同步", r"交付", r"复制到", r"cp\b", r"rsync",
    r"copy", r"sync", r"deliver",
    # Simple commands
    r"启动", r"停止", r"重启", r"杀死", r"关闭",
    r"start", r"stop", r"restart", r"kill",
    # Status / list / info
    r"列出", r"查看", r"显示", r"有什么",
    r"list", r"show", r"status", r"ls\b",
    # Confirmation / simple replies
    r"好的", r"可以", r"继续", r"试一下",
    r"ok", r"yes", r"go ahead", r"try",
    r"多少钱", r"余额", r"balance", r"cost",
    # Time / simple query
    r"几点了", r"时间", r"time",
    # Model switch itself
    r"切换.*模型", r"switch.*model", r"h-model",
    r"用什么模型", r"当前.*模型",
]

# Explicit user overrides in message body
_REMOTE_OVERRIDE = re.compile(
    r"(用(DeepSeek|远程|贵的|付费|网上)|"
    r"use\s+(DeepSeek|remote|paid|api)|"
    r"让\w*(聪明|强|厉害).*(来|做))",
    re.IGNORECASE,
)
_LOCAL_OVERRIDE = re.compile(
    r"(用(本地|免费的|Ollama|Qwen|省钱)|"
    r"use\s+(local|ollama|qwen|free)|"
    r"本地.*(跑|做|处理))",
    re.IGNORECASE,
)


# ── Scoring Engine ───────────────────────────────────────────


def _keyword_score(text: str) -> Tuple[int, int, str]:
    """Score message complexity. Returns (score, matched_count, reason).

    Score range: 0-100
      0-20  → local model (trivial)
      21-50 → local model (simple)
      51-70 → borderline → can be local or remote
      71-100 → remote model (complex)

    Returns:
      (score, matched_count, reason_string)
    """
    score = 0
    reasons = []
    matched_high = 0
    matched_low = 0

    # 1. Length factor (0-40 points)
    length = len(text)
    if length > 300:
        score += 40
        reasons.append(f"long({length}chars)")
    elif length > 200:
        score += 30
        reasons.append(f"long({length}chars)")
    elif length > 100:
        score += 20
        reasons.append(f"medium({length}chars)")
    elif length > 50:
        score += 10
        reasons.append(f"medium({length}chars)")
    elif length > 20:
        score += 5
    # short messages (≤20) get 0 from length

    # 2. High-complexity keywords (0-80 points)
    for kw in _HIGH_KEYWORDS:
        if re.search(kw, text):
            # Debug/error/crash keywords carry more weight
            if kw in (
                r"为什么.*(不|没|失败|报错|error)",
                r"fix.*bug", r"debug",
                r"traceback", r"crash", r"崩溃", r"异常",
                r"error\b", r"bug\b",
                r"设计", r"架构", r"规划", r"方案",
                r"重构", r"整体",
                r"analyze", r"architecture",
                r"refactor",
            ):
                score += 25
            else:
                score += 15
            matched_high += 1
            reasons.append(f"H:{kw[:12]}")

    # 3. Low-complexity keywords (negative, -10 each, max -30)
    for kw in _LOW_KEYWORDS:
        if re.search(kw, text):
            score -= 10
            matched_low += 1
            reasons.append(f"L:{kw[:12]}")

    # 4. Questions that imply complex reasoning
    question_markers = [
        r"为什么", r"怎么(办|做|实现|解决)",
        r"how\s+(to|do|can|would)", r"what\s+is\s+the\s+(best|difference|problem)",
        r"should\s+I", r"which\s+(one|approach)",
        r"crash", r"error", r"bug", r"失败", r"报错",
    ]
    for qm in question_markers:
        if re.search(qm, text):
            score += 10
            matched_high += 1
            reasons.append(f"Q:{qm[:10]}")
            break  # Only count once

    # Clamp
    score = max(0, min(100, score))

    # Determine tier label
    if score <= 20:
        tier = "trivial"
    elif score <= 50:
        tier = "simple"
    elif score <= 70:
        tier = "borderline"
    else:
        tier = "complex"

    return score, matched_high - matched_low, f"{tier}({score}):{'|'.join(reasons[:6])}"


def _check_override(text: str) -> Optional[str]:
    """Check if user explicitly requests a model tier. Returns 'local' or 'remote' or None."""
    if _REMOTE_OVERRIDE.search(text):
        return "remote"
    if _LOCAL_OVERRIDE.search(text):
        return "local"
    return None


def _has_attachments(msg: dict) -> bool:
    """Check if message has image attachments (needs vision model)."""
    atts = msg.get("attachments") or msg.get("file_ids") or []
    if atts:
        return True
    return False


# ── Routing Decision ─────────────────────────────────────────


def decide_routing(
    message: str,
    msg_dict: Optional[dict] = None,
    active_profile: Optional[dict] = None,
    profiles: Optional[dict] = None,
) -> dict:
    """Make routing decision for a user message.

    Args:
      message: The user's text message.
      msg_dict: Full message dict (may contain attachments, file_ids, etc.)
      active_profile: Current active model profile from model_switch.
      profiles: Full model_profiles.json data (with "profiles" key).
                 Passed from caller to avoid importing model_switch directly.

    Returns:
      {
        "target_tier": "local" | "remote",
        "score": int (0-100),
        "reason": str,
        "needs_switch": bool,  # True if we need to switch model
        "target_profile_id": str | None,
        "override": str | None,  # "user_remote", "user_local", "auto", None
      }
    """
    result = {
        "target_tier": "remote",
        "score": 50,
        "reason": "default",
        "needs_switch": False,
        "target_profile_id": None,
        "override": None,
    }

    # ── Phase 1: Check explicit user override ──
    override = _check_override(message)
    if override:
        result["target_tier"] = override
        result["override"] = f"user_{override}"
        result["reason"] = f"User explicitly requested {override} model"
        result["score"] = 80 if override == "remote" else 20
    else:
        # ── Phase 2: Score-based decision ──
        score, _, reason_str = _keyword_score(message)
        result["score"] = score

        # ── Phase 2b: Learned corrections override (if confident) ──
        learned_tier = score_message(message)
        if learned_tier and learned_tier != result.get("target_tier", ""):
            if (
                (learned_tier == "local" and score <= 30)
                or (learned_tier == "remote" and score >= 50)
            ):
                # Correction agrees with score → boost confidence, keep existing
                result["reason"] = f"{reason_str} + learned:{learned_tier}"
            else:
                # Correction disagrees → trust learned pattern
                result["target_tier"] = learned_tier
                result["reason"] = f"Learned correction → {learned_tier} (score={score})"

        # Attachments need vision-capable model — route to qwen3.6:27b (128K ctx, vision)
        has_att = _has_attachments(msg_dict or {})

        if has_att:
            # Image analysis → route local (qwen3.6 has vision support + 128K ctx)
            result["target_tier"] = "local"
            result["reason"] = f"Has attachments + score={score}: use local vision (qwen3.6:27b)"
        elif score <= 20:
            # Trivial task → definitely local
            result["target_tier"] = "local"
            result["reason"] = reason_str
        elif score <= 30:
            # Simple task → local, unless already on remote (avoid flip-flop)
            if active_profile and active_profile.get("type") == "remote":
                result["target_tier"] = "remote"
                result["reason"] = f"Simple({score}) but already on remote — keep to avoid switch"
            else:
                result["target_tier"] = "local"
                result["reason"] = reason_str
        elif score <= 50 and active_profile and active_profile.get("cost_tier") == "free":
            # If already on a free model, keep it for borderline tasks
            result["target_tier"] = "local"
            result["reason"] = f"Borderline({score}) + already on local"
        else:
            result["target_tier"] = "remote"
            result["reason"] = reason_str

    result["override"] = result.get("override") or "auto"

    # ── Phase 3: Determine if switch needed ──
    if active_profile:
        current_is_local = active_profile.get("type") == "local"
        target_is_local = result["target_tier"] == "local"

        # We need to find the right profile_id
        if target_is_local and not current_is_local:
            # Need to switch to a local model
            result["needs_switch"] = True
            result["target_profile_id"] = _pick_local_profile(active_profile, profiles or {})
        elif not target_is_local and current_is_local:
            # Need to switch back to remote
            result["needs_switch"] = True
            result["target_profile_id"] = _pick_remote_profile(active_profile, profiles or {})
    else:
        # No active profile → we need to decide what to suggest
        result["needs_switch"] = False  # Can't switch without profiles

    return result


def _pick_local_profile(current: dict, profiles: dict) -> Optional[str]:
    """Pick the best local profile from given profiles dict.

    Prefers qwen3.6-27b-q4_K_M (best local model available with vision + 128K ctx).
    Falls back to any local/free profile.
    """
    try:
        profiles_dict = profiles.get("profiles", {}) if profiles else {}

        # Preference order
        preferred = ["qwen3.6-27b-q4_K_M", "qwen2.5-coder-14b", "qwen2.5-14b", "llava-7b"]
        for pid in preferred:
            if pid in profiles_dict:
                p = profiles_dict[pid]
                if p.get("type") == "local" or p.get("cost_tier") == "free":
                    return pid

        # Any local/free profile
        for pid, p in profiles_dict.items():
            if p.get("type") == "local" or p.get("cost_tier") == "free":
                return pid
    except Exception:
        pass
    return None


def _pick_remote_profile(current: dict, profiles: dict) -> Optional[str]:
    """Pick the best remote profile from given profiles dict.

    Prefers deepseek-chat.
    """
    try:
        profiles_dict = profiles.get("profiles", {}) if profiles else {}

        preferred = ["deepseek-chat", "deepseek-reasoner"]
        for pid in preferred:
            if pid in profiles_dict:
                return pid

        for pid, p in profiles_dict.items():
            if p.get("type") == "remote" or p.get("cost_tier") == "paid":
                return pid
    except Exception:
        pass
    return None


# ── Public API ──────────────────────────────────────────────


def get_routing_status(active_profile: Optional[dict] = None) -> dict:
    """Get current routing status for frontend LED indicator.

    Returns:
      {
        "tier": "local" | "remote" | "unknown",
        "active_profile": {...} | None,
        "ollama_connected": bool,
      }
    """
    if not active_profile:
        return {"tier": "unknown", "active_profile": None, "ollama_connected": False}

    is_local = active_profile.get("type") == "local"
    return {
        "tier": "local" if is_local else "remote",
        "active_profile": active_profile,
        "ollama_connected": _check_ollama(),
    }
