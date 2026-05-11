"""Smoke tests for the admin FastAPI app.

Verifies the admin module assembles: all imports resolve, Starlette-Admin
accepts the ModelView definitions, auth provider initializes from settings,
and the admin sub-app mounts onto FastAPI.
"""

from src.presentation.admin.main import create_app


def test_admin_app_creates_without_errors() -> None:
    app = create_app()
    assert app is not None


def test_admin_routes_mounted() -> None:
    app = create_app()
    route_paths = [getattr(route, "path", "") for route in app.routes]
    assert any("admin" in str(path).lower() for path in route_paths)
