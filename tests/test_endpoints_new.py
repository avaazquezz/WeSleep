import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.models import SleepRecord
from datetime import datetime
from uuid import uuid4

@pytest.mark.asyncio
async def test_health_check():
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_ingestion_and_smart_alarm():
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Ingest Data
            record_id = str(uuid4())
            payload = {
                "record_id": record_id,
                "modified_at": "2025-04-30T12:00:26Z",
                "start_at_timestamp": "2025-04-28T17:30:00Z",
                "end_at_timestamp": "2025-04-29T03:34:00Z",
                "duration": 36240000,
                "metrics": {
                    "heartrate": 56,
                    "sleep_duration": 25920000,
                    "hrv_sdnn": 50,
                    "sleep_duration_deep": 10000,
                    "sleep_duration_light": 10000,
                    "sleep_duration_rem": 5000,
                    "sleep_duration_awake": 920
                },
                "provider_source": "test_provider",
                "provider_slug": "test",
                "source": {
                   "source_version": "1.0",
                   "source_bundle_identifier": "com.test"
                }
            }
            
            response = await ac.post("/api/v1/webhooks/wearable/", json=payload)
            assert response.status_code == 200
            ingested_id = response.json()
            assert ingested_id is not None
    
            # 2. Predict Smart Alarm
            alarm_request = {
                "sleep_record_id": ingested_id,
                "target_time": "2025-04-29T07:00:00Z"
            }
            response = await ac.post("/api/v1/sleep/smart-alarm", json=alarm_request)
            if response.status_code != 200:
                 print(response.json())
            assert response.status_code == 200
            data = response.json()
            assert "suggested_time" in data
            assert "quality_score" in data
            assert "anomalies" in data
            assert data["confidence"] > 0.0
