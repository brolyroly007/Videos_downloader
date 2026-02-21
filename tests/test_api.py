"""
Tests for FastAPI endpoints defined in app.py.

Uses httpx.AsyncClient with ASGITransport so every request goes through
the ASGI interface without starting a real server.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_root_endpoint():
    """GET / must return 200 (HTML dashboard page)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_info():
    """GET /api/info must return 200 with title and version keys."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/info")

    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_list_downloads():
    """GET /api/files/downloads must return 200 with a files list."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/files/downloads")

    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert isinstance(data["files"], list)


@pytest.mark.asyncio
async def test_list_processed():
    """GET /api/files/processed must return 200 with a files list."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/files/processed")

    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert isinstance(data["files"], list)


@pytest.mark.asyncio
async def test_download_missing_url():
    """POST /api/download with an empty body must return 422 (validation error)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/api/download", json={})

    assert response.status_code == 422
