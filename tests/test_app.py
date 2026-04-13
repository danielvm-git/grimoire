"""Tests for the FastAPI app factory."""

from __future__ import annotations

from httpx import AsyncClient


async def test_root_returns_ok(async_client: AsyncClient) -> None:
    resp = await async_client.get("/")
    assert resp.status_code == 200
    # Dashboard now returns HTML
    assert "text/html" in resp.headers.get("content-type", "")


async def test_health_returns_ok(async_client: AsyncClient) -> None:
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
