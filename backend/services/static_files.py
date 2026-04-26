"""
Hermes WebUI — Static Files Service
Custom StaticFiles subclass for development-friendly caching.
"""
from fastapi.staticfiles import StaticFiles


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles subclass that always returns Cache-Control: no-store, no-cache.
    Prevents the sandbox browser environment from caching stale JS modules."""
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
