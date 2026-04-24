"""
Tests for memory system endpoints.
"""

import pytest


class TestMemories:
    """Test memory read/write operations."""

    def test_get_memories(self, client):
        """Should return all memory files."""
        resp = client.get("/api/memories")
        assert resp.status_code == 200
        data = resp.json()
        assert "SOUL.md" in data
        assert "MEMORY.md" in data
        assert "USER.md" in data

    def test_update_memory(self, client):
        """Should write to a valid memory file."""
        resp = client.put("/api/memories/SOUL.md", json={
            "content": "# Test Soul\nI am a test agent.",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Verify the write
        resp = client.get("/api/memories")
        assert "Test Soul" in resp.json()["SOUL.md"]

    def test_update_invalid_memory_file(self, client):
        """Should reject invalid memory filenames."""
        resp = client.put("/api/memories/EVIL.md", json={
            "content": "hack",
        })
        assert resp.status_code == 400

    def test_update_memory_path_traversal(self, client):
        """Should reject path traversal attempts."""
        resp = client.put("/api/memories/..%2F..%2Fetc%2Fpasswd", json={
            "content": "hack",
        })
        # Should be rejected as invalid filename (not SOUL.md/MEMORY.md/USER.md)
        assert resp.status_code in (400, 404, 405, 422)

    def test_update_memory_too_long(self, client):
        """Should reject content exceeding max length."""
        resp = client.put("/api/memories/SOUL.md", json={
            "content": "x" * 200000,
        })
        assert resp.status_code == 422  # Pydantic validation


class TestSkills:
    """Test skills endpoints."""

    def test_list_skills(self, client):
        """Should return skills list."""
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert isinstance(data["skills"], list)
