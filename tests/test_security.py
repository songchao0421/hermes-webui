"""
Tests for security measures: path traversal, input validation, etc.
"""

import pytest


class TestAvatarSecurity:
    """Test avatar upload and serving security."""

    def test_avatar_nonexistent_file(self, client):
        """Should return 404 for nonexistent avatar files."""
        resp = client.get("/api/persona/avatar/nonexistent_file.png")
        assert resp.status_code == 404

    def test_avatar_path_traversal_backslash(self, client):
        """Should reject filenames with backslashes."""
        resp = client.get("/api/persona/avatar/..\\..\\etc\\passwd")
        assert resp.status_code in (400, 404)

    def test_avatar_path_traversal_dotdot(self, client):
        """Should reject filenames with double dots."""
        resp = client.get("/api/persona/avatar/..avatar.png")
        assert resp.status_code in (400, 404)


class TestInputValidation:
    """Test input validation for various endpoints."""

    def test_chat_empty_message(self, client):
        """Should reject empty messages."""
        resp = client.post("/api/agent/stream", json={
            "message": "",
        })
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_chat_message_too_long(self, client):
        """Should reject messages exceeding max length."""
        resp = client.post("/api/agent/stream", json={
            "message": "x" * 40000,
        })
        assert resp.status_code == 422  # Pydantic max_length=32000

    def test_agent_empty_message(self, client):
        """Should reject empty agent messages."""
        resp = client.post("/api/agent/stream", json={
            "message": "",
        })
        assert resp.status_code == 422

    def test_persona_name_max_length(self, client):
        """Should reject names exceeding 50 chars."""
        resp = client.put("/api/persona", json={
            "agent_name": "N" * 51,
        })
        assert resp.status_code == 422
