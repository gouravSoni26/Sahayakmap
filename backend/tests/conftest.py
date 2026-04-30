"""
Shared pytest fixtures and session-level checks for integration tests.
"""
import pytest
import httpx


BASE_URL = "http://localhost:8000"


def pytest_configure(config):
    """Fail the session immediately if the backend isn't reachable."""
    try:
        resp = httpx.get(f"{BASE_URL}/api/health", timeout=3.0)
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.exit(
            f"\n\nBackend not reachable at {BASE_URL}.\n"
            "Start it first:\n\n"
            "  cd backend && venv/Scripts/uvicorn main:app --reload --port 8000\n",
            returncode=1,
        )
    except httpx.HTTPStatusError as exc:
        pytest.exit(
            f"\n\nBackend returned {exc.response.status_code} on /api/health.\n"
            "Check the server logs for startup errors.\n",
            returncode=1,
        )
