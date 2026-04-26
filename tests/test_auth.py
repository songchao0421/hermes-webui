"""
Tests for authentication module.
"""

import pytest
from fastapi.testclient import TestClient


class TestAuth:
    """Test API token authentication."""

    def test_health_no_auth(self, client):
        """Health endpoint should work without auth."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_api_without_auth_disabled(self, client):
        """API should work when auth is disabled."""
        resp = client.get("/api/persona")
        assert resp.status_code == 200

    def test_api_requires_auth_when_enabled(self):
        """API should return 401 when auth is enabled and no token provided."""
        from auth import set_auth_enabled
        from app import app

        set_auth_enabled(True)
        try:
            with TestClient(app) as c:
                resp = c.get("/api/persona")
                assert resp.status_code == 401
        finally:
            set_auth_enabled(False)

    def test_api_with_valid_token(self, auth_client):
        """API should work with valid Bearer token."""
        resp = auth_client.get("/api/persona")
        assert resp.status_code == 200

    def test_api_with_invalid_token(self):
        """API should reject invalid tokens."""
        from auth import set_auth_enabled
        from app import app

        set_auth_enabled(True)
        try:
            with TestClient(app) as c:
                c.headers["Authorization"] = "Bearer invalid_token_12345"
                resp = c.get("/api/persona")
                assert resp.status_code == 401
        finally:
            set_auth_enabled(False)

    def test_token_generation(self, token):
        """Generated token should be non-empty and URL-safe."""
        assert len(token) > 20
        # URL-safe base64 characters
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', token)

    def test_token_persistence(self):
        """Token should be the same across calls."""
        from auth import get_or_create_token
        t1 = get_or_create_token()
        t2 = get_or_create_token()
        assert t1 == t2
