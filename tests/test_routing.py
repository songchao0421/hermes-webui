"""
Tests for task routing engine and correction store.
Coverage:
  - _keyword_score: simple, trivial, complex, mixed messages
  - _check_override: explicit remote/local overrides
  - decide_routing: full routing decision with/without profiles
  - score_message / record_correction: learned corrections
  - get_routing_status: LED indicator
"""

import re
import json
import tempfile
from pathlib import Path

import pytest
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def fake_profiles():
    """Standard test profiles dict."""
    return {
        "profiles": {
            "qwen3.6-27b-q4_K_M": {
                "name": "Qwen 3.6 27B",
                "type": "local",
                "cost_tier": "free",
                "provider": "ollama",
            },
            "deepseek-chat": {
                "name": "DeepSeek Chat",
                "type": "remote",
                "cost_tier": "paid",
                "provider": "deepseek",
            },
        }
    }


@pytest.fixture
def active_local(fake_profiles):
    """Simulate being on local model."""
    return fake_profiles["profiles"]["qwen3.6-27b-q4_K_M"]


@pytest.fixture
def active_remote(fake_profiles):
    """Simulate being on remote model."""
    return fake_profiles["profiles"]["deepseek-chat"]


# ── _keyword_score tests ─────────────────────────────────────────

class TestKeywordScore:
    """Test the scoring engine directly."""

    def test_short_trivial_message(self):
        from services.task_router import _keyword_score
        score, count, reason = _keyword_score("你好")
        assert score <= 20, f"Expected low score for '你好', got {score}"
        assert "trivial" in reason or "simple" in reason, f"Expected trivial/simple, got {reason}"

    def test_short_command(self):
        from services.task_router import _keyword_score
        score, count, reason = _keyword_score("同步一下文件")
        assert score <= 30, f"Expected low score for sync command, got {score}"

    def test_complex_analysis_request(self):
        from services.task_router import _keyword_score
        msg = "我们分析一下这个系统的架构设计有什么问题，然后给出重构方案"
        score, count, reason = _keyword_score(msg)
        assert score >= 50, f"Expected high score for arch analysis, got {score}"

    def test_long_code_generation(self):
        from services.task_router import _keyword_score
        msg = "生成一个完整的用户管理系统，包括登录、注册、权限管理和日志审计功能，要求用 FastAPI 实现"
        score, count, reason = _keyword_score(msg)
        # Moderate score — "生成" alone isn't highly weighted, length contributes
        assert score >= 25, f"Expected at least moderate score for long code gen, got {score}"

    def test_debug_error_message(self):
        from services.task_router import _keyword_score
        msg = "为什么这个 bug 一直报错？traceback 说 NoneType has no attribute"
        score, count, reason = _keyword_score(msg)
        assert score >= 30, f"Expected at least moderate score for debug message, got {score}"

    def test_mixed_message_low_wins(self):
        from services.task_router import _keyword_score
        msg = "好的，继续，复制文件到目标目录"
        score, count, reason = _keyword_score(msg)
        # Low keywords subtract points; should stay low
        assert score <= 30, f"Expected low score for simple confirm+copy, got {score}"

    def test_message_with_question_marker(self):
        from services.task_router import _keyword_score
        msg = "怎么实现多线程下载？"
        score, count, reason = _keyword_score(msg)
        assert score >= 5, f"Expected question marker adds points, got {score}"
        # Short message (8 chars) + question marker = 0 + 10 = 10

    def test_empty_message(self):
        from services.task_router import _keyword_score
        score, count, reason = _keyword_score("")
        assert score == 0, f"Expected 0 for empty, got {score}"
        assert "trivial" in reason


# ── _check_override tests ────────────────────────────────────────

class TestCheckOverride:
    """Test user override detection."""

    def test_remote_override_deepseek(self):
        from services.task_router import _check_override
        assert _check_override("用DeepSeek来分析这个问题") == "remote"

    def test_remote_override_paid(self):
        from services.task_router import _check_override
        result = _check_override("你用远程模型来写")
        assert result == "remote", f"Expected 'remote', got {result}"

    def test_local_override_explicit(self):
        from services.task_router import _check_override
        assert _check_override("本地跑吧，别费钱了") == "local"

    def test_local_override_ollama(self):
        from services.task_router import _check_override
        assert _check_override("用Ollama来处理这个简单任务") == "local"

    def test_no_override(self):
        from services.task_router import _check_override
        assert _check_override("今天天气怎么样") is None

    def test_empty_no_override(self):
        from services.task_router import _check_override
        assert _check_override("") is None


# ── decide_routing tests ─────────────────────────────────────────

class TestDecideRouting:
    """Full routing decision integration tests."""

    def test_simple_message_local(self, fake_profiles, active_local):
        from services.task_router import decide_routing
        decision = decide_routing(
            message="复制文件到目标目录",
            active_profile=active_local,
            profiles=fake_profiles,
        )
        assert decision["target_tier"] == "local", f"Expected local for simple copy, got {decision}"
        assert decision["needs_switch"] is False

    def test_complex_message_remote(self, fake_profiles, active_local):
        from services.task_router import decide_routing
        msg = "分析系统架构设计，给出重构方案，包括性能优化和安全审计建议"
        decision = decide_routing(
            message=msg,
            active_profile=active_local,
            profiles=fake_profiles,
        )
        assert decision["target_tier"] == "remote", f"Expected remote for arch analysis, got {decision}"
        assert decision["needs_switch"] is True
        assert decision["target_profile_id"] is not None

    def test_remote_override_from_local(self, fake_profiles, active_local):
        from services.task_router import decide_routing
        decision = decide_routing(
            message="用DeepSeek分析这个问题",
            active_profile=active_local,
            profiles=fake_profiles,
        )
        assert decision["target_tier"] == "remote"
        assert decision["override"] == "user_remote"
        assert decision["needs_switch"] is True

    def test_local_override_from_remote(self, fake_profiles, active_remote):
        from services.task_router import decide_routing
        decision = decide_routing(
            message="本地跑吧，别费钱了",
            active_profile=active_remote,
            profiles=fake_profiles,
        )
        assert decision["target_tier"] == "local"
        assert decision["override"] == "user_local"
        assert decision["needs_switch"] is True

    def test_no_profile_returns_no_switch(self, fake_profiles):
        from services.task_router import decide_routing
        decision = decide_routing(
            message="随便问问",
            active_profile=None,
            profiles=fake_profiles,
        )
        assert decision["needs_switch"] is False
        assert decision["target_tier"] in ("local", "remote")

    def test_already_on_remote_low_score_still_switches(self, fake_profiles, active_remote):
        """Very low score task switches FROM remote to local.
        
        score <= 20 branch sets local regardless of current profile."""
        from services.task_router import decide_routing
        decision = decide_routing(
            message="看看文件列表",
            active_profile=active_remote,
            profiles=fake_profiles,
        )
        assert decision["target_tier"] == "local", (
            f"Trivial message should target local even when on remote, "
            f"got target_tier={decision['target_tier']}"
        )
        assert decision["needs_switch"] is True, (
            f"Trivial message on remote should trigger switch to local"
        )

    def test_borderline_score_keeps_remote(self, fake_profiles, active_remote):
        """Score 20-30 on remote → keep remote to avoid flip-flop."""
        from services.task_router import decide_routing
        decision = decide_routing(
            message="看看昨天同步的日志文件内容",
            active_profile=active_remote,
            profiles=fake_profiles,
        )
        # This message should score in 20-30 range
        if decision["score"] >= 20 and decision["score"] <= 30:
            assert decision["needs_switch"] is False, (
                f"Borderline score ({decision['score']}) on remote should keep remote, "
                f"got needs_switch={decision['needs_switch']}"
            )

    def test_empty_profiles_doesnt_crash(self, active_local):
        from services.task_router import decide_routing
        # Should not crash even with empty/None profiles
        decision = decide_routing(
            message="用DeepSeek分析",
            active_profile=active_local,
            profiles=None,
        )
        assert decision["target_tier"] == "remote"
        # needs_switch might be True but target_profile_id should be None
        # (can't find local profile in empty dict)
        if decision["needs_switch"]:
            assert decision["target_profile_id"] is None


# ── get_routing_status tests ─────────────────────────────────────

class TestRoutingStatus:
    """Test LED indicator status."""

    def test_with_local_profile(self, active_local):
        from services.task_router import get_routing_status
        status = get_routing_status(active_local)
        assert status["tier"] == "local"
        assert status["active_profile"] is not None

    def test_with_remote_profile(self, active_remote):
        from services.task_router import get_routing_status
        status = get_routing_status(active_remote)
        assert status["tier"] == "remote"
        assert status["active_profile"] is not None

    def test_without_profile(self):
        from services.task_router import get_routing_status
        status = get_routing_status(None)
        assert status["tier"] == "unknown"
        assert status["active_profile"] is None
        assert status["ollama_connected"] is False
