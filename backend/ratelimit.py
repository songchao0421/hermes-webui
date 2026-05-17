"""
Rate Limiting Module (Hermes WebUI)

Replaces the old slowapi Limiter._dependency() pattern which was removed in slowapi>=0.1.9.
Provides fastapi.Depends-compatible callables for per-route rate limiting using the 
limits library directly (no dependency on slowapi's internal API).

X-Forwarded-For 安全说明:
  默认情况下（TRUSTED_PROXIES 为空），X-Forwarded-For 被忽略。
  仅在可信代理列表非空时信任此头部。
  这是为了防止客户端伪造 X-Forwarded-For 绕过速率限制。

Usage:
    from ratelimit import RateLimit, RateLimitExceeded

    @router.post("/chat")
    async def chat(request: Request, _: None = Depends(RateLimit("60/minute"))):
        ...

Or with the router pattern (post-creation dependency injection):
    router.routes[0].dependencies = [Depends(RateLimit("60/minute"))]
"""

from typing import Optional
from fastapi import Request
from starlette.responses import JSONResponse
from limits.strategies import STRATEGIES
from limits.storage import MemoryStorage
from limits import parse_many, RateLimitItem


# ── Singleton storage & strategy ──────────────────────────────────
# In-memory storage is fine for single-process deployments.
# For multi-process, swap to RedisStorage("redis://...") here.
_storage = MemoryStorage()
_strategy = STRATEGIES["moving-window"](_storage)


class RateLimitExceeded(Exception):
    """Raised when a client exceeds their rate limit."""
    def __init__(self, limit: str):
        self.limit = limit
        super().__init__(f"Rate limit exceeded: {limit}")


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """FastAPI exception handler for RateLimitExceeded."""
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc)},
        headers={"Retry-After": "60"},
    )


def RateLimit(limit_string: str, scope: str = "global", key_func=None):
    """
    Create a FastAPI dependency callable that enforces the given rate limit.

    Args:
        limit_string: e.g. "60/minute", "10/minute", "5/second"
        scope: namespace for the counter (default "global")
        key_func: callable(request) -> str, defaults to client IP

    Returns:
        A callable suitable for use with FastAPI's Depends().
    """
    limit_items: list[RateLimitItem] = list(parse_many(limit_string))

    async def _rate_limit_dep(request: Request) -> None:
        if _is_disabled():
            return
        client_key = (key_func(request) if key_func else _client_ip(request))
        for item in limit_items:
            if not _strategy.hit(item, client_key, scope):
                raise RateLimitExceeded(limit_string)

    return _rate_limit_dep


# ── Helpers ────────────────────────────────────────────────────────

_enabled = True

def disable_rate_limits():
    """Globally disable all rate limiting. Useful for tests or --no-auth mode."""
    global _enabled
    _enabled = False

def enable_rate_limits():
    global _enabled
    _enabled = True

def _is_disabled() -> bool:
    return not _enabled

def _client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies.

    X-Forwarded-For 只在直连 IP 属于可信代理时才被信任，
    否则忽略（防止伪造 IP 绕过速率限制）。
    """
    direct_ip = request.client.host if request.client else "unknown"

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded and direct_ip != "unknown":
        from config import get_trusted_proxies
        trusted = get_trusted_proxies()
        if trusted and direct_ip in trusted:
            return forwarded.split(",")[0].strip()

    return direct_ip


# ── Pre-built limit callables (for convenience) ────────────────────
# These are plain callables, not functions that return callables.
# Usage: router.routes[0].dependencies = [Depends(limit_60_per_minute)]

def _make_simple_rate_limit(limit_string: str):
    """Create a simple callable (not a factory) for a fixed limit string."""
    limit_items = list(parse_many(limit_string))
    async def _check(request: Request) -> None:
        if _is_disabled():
            return
        client_key = _client_ip(request)
        for item in limit_items:
            if not _strategy.hit(item, client_key, "global"):
                raise RateLimitExceeded(limit_string)
    return _check

limit_10_per_minute  = _make_simple_rate_limit("10/minute")
limit_20_per_minute  = _make_simple_rate_limit("20/minute")
limit_60_per_minute  = _make_simple_rate_limit("60/minute")
limit_5_per_second   = _make_simple_rate_limit("5/second")


# ── User-aware rate limit (keyed by auth_user instead of IP) ─────────

def _user_key(request: Request) -> str:
    """Extract auth username as rate limit key. Falls back to IP."""
    username = getattr(request.state, "auth_user", None)
    if username:
        return f"user:{username}"
    return _client_ip(request)


async def _limit_agent_stream(request: Request) -> None:
    """User-level rate limit for SSE agent stream: 10/minute per user."""
    if _is_disabled():
        return
    client_key = _user_key(request)
    items = list(parse_many("10/minute"))
    for item in items:
        if not _strategy.hit(item, client_key, "agent_stream"):
            raise RateLimitExceeded("10/minute")
