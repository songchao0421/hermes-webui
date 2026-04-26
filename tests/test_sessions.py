"""
Tests for session management endpoints.
"""

import pytest


class TestSessions:
    """Test session CRUD operations."""

    def test_list_sessions(self, client):
        """Should return sessions list."""
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "current" in data

    def test_create_session(self, client):
        """Should create a new session."""
        resp = client.post("/api/sessions/new")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_get_session_messages(self, client):
        """Should return messages for a session."""
        # Create session first
        create_resp = client.post("/api/sessions/new")
        session_id = create_resp.json()["session_id"]

        resp = client.get(f"/api/sessions/{session_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)

    def test_delete_session(self, client):
        """Should delete a session."""
        # Create session first
        create_resp = client.post("/api/sessions/new")
        session_id = create_resp.json()["session_id"]

        resp = client.delete(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
