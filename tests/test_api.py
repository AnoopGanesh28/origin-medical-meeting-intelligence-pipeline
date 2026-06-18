import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_api_missing_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Missing X-API-Key header
        resp = await client.post("/process-meeting", json={"transcript_text": "Alice: Bob will fix the bugs."})
        assert resp.status_code == 422 # FastAPI validation error for missing required header
        
        # Invalid X-API-Key header
        resp2 = await client.post("/process-meeting", json={"transcript_text": "Alice: Bob will fix the bugs."}, headers={"X-API-Key": "invalid_key"})
        assert resp2.status_code == 401

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
