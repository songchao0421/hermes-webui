"""
Tests for persona/personalization endpoints.
"""

import pytest


class TestPersona:
    """Test persona CRUD operations."""

    def test_get_persona(self, client):
        """Should return persona with default fields."""
        resp = client.get("/api/persona")
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_name" in data
        assert "theme" in data
        assert "theme_presets" in data

    def test_update_persona_name(self, client):
        """Should update agent name."""
        resp = client.put("/api/persona", json={
            "agent_name": "TestBot",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["persona"]["agent_name"] == "TestBot"

    def test_update_persona_theme_preset(self, client):
        """Should update theme to a valid preset."""
        resp = client.put("/api/persona", json={
            "theme": {"preset": "cyan"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["persona"]["theme"]["preset"] == "cyan"
        assert data["persona"]["theme"]["accent"] == "#00daf3"

    def test_update_persona_custom_theme(self, client):
        """Should accept custom theme color."""
        resp = client.put("/api/persona", json={
            "theme": {"preset": "custom", "accent": "#ff0000"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["persona"]["theme"]["accent"] == "#ff0000"

    def test_update_persona_name_too_long(self, client):
        """Should reject names exceeding max length."""
        resp = client.put("/api/persona", json={
            "agent_name": "A" * 100,
        })
        assert resp.status_code == 422  # Pydantic validation error

    def test_update_setup_complete(self, client):
        """Should mark setup as complete."""
        resp = client.put("/api/persona", json={
            "setup_complete": True,
        })
        assert resp.status_code == 200
        assert resp.json()["persona"]["setup_complete"] is True
