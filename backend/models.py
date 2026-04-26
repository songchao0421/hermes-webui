"""
Hermes WebUI - Pydantic Request/Response Models
Type-safe API contracts with input validation.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ── Chat ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32000)
    model: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    content: str
    model: str
    latency_ms: int
    session_id: str


# ── Agent ────────────────────────────────────────────────────────

class AgentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32000)
    session_id: Optional[str] = None
    system_message: Optional[str] = Field(None, max_length=32000)
    history: Optional[list[dict]] = None
    file_ids: Optional[list[str]] = None


# ── Persona ──────────────────────────────────────────────────────

class ThemeConfig(BaseModel):
    accent: Optional[str] = Field(None, max_length=20)
    accent_dim: Optional[str] = Field(None, max_length=20)
    preset: Optional[str] = Field(None, max_length=20)


class PersonaUpdate(BaseModel):
    agent_name: Optional[str] = Field(None, max_length=50)
    agent_subtitle: Optional[str] = Field(None, max_length=100)
    user_display_name: Optional[str] = Field(None, max_length=50)
    avatar: Optional[str] = None
    user_avatar: Optional[str] = None
    avatar_preset: Optional[str] = Field(None, max_length=20)
    setup_complete: Optional[bool] = None
    theme: Optional[ThemeConfig] = None


# ── Memory ───────────────────────────────────────────────────────

class MemoryUpdate(BaseModel):
    content: str = Field(..., max_length=100000)
