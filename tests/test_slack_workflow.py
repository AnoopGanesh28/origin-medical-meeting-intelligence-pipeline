import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
import time

@pytest.mark.asyncio
async def test_slack_interaction_invalid_signature():
    # Force a secret to ensure verification is active
    saved_secret = settings.SLACK_SIGNING_SECRET
    settings.SLACK_SIGNING_SECRET = "secret_for_test"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Valid looking payload but invalid signature
        payload = "payload=%7B%22type%22%3A%22block_actions%22%7D"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": str(int(time.time())),
            "X-Slack-Signature": "v0=badsignature"
        }
        
        resp = await client.post("/slack/interactions", content=payload, headers=headers)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Invalid Slack signature"
        
    settings.SLACK_SIGNING_SECRET = saved_secret

@pytest.mark.asyncio
async def test_slack_interaction_missing_payload():
    saved_secret = settings.SLACK_SIGNING_SECRET
    settings.SLACK_SIGNING_SECRET = "" # Disable sig check for payload structural test
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/slack/interactions", content=b"", headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Missing payload field"
        
    settings.SLACK_SIGNING_SECRET = saved_secret
