from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Patient, SleepRecord, Tenant


@pytest.mark.asyncio
async def test_mock_webhook_inserts_sleep_record(async_client, session_maker):
    async with session_maker() as session:  # type: AsyncSession
        tenant = Tenant(name="T", api_key="t_api")
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

        patient = Patient(tenant_id=tenant.id, internal_mock_id="mock_healthy")
        session.add(patient)
        await session.commit()
        await session.refresh(patient)

    payload = {
        "internal_mock_id": "mock_healthy",
        "date": date.today().isoformat(),
        "duration": 7 * 60 * 60 * 1000,
        "hypnogram": [
            {"start_time": "23:00", "end_time": "01:00", "phase": "light"},
            {"start_time": "01:00", "end_time": "02:30", "phase": "deep"},
            {"start_time": "02:30", "end_time": "06:50", "phase": "rem"},
            {"start_time": "06:50", "end_time": "07:00", "phase": "awake"},
        ],
        "avg_hr": 55.0,
        "hrv": 70.0,
        "spo2": 97.0,
    }

    resp = await async_client.post("/api/v1/wearable/mock-webhook", json=payload)
    assert resp.status_code == 200, resp.text
    record_id = resp.json()
    assert isinstance(record_id, str)

    async with session_maker() as session:
        result = await session.exec(select(SleepRecord).where(SleepRecord.id == record_id))
        record = result.first()
        assert record is not None
        assert record.patient_id == patient.id
        assert record.date == date.today()
        assert record.payload["internal_mock_id"] == "mock_healthy"


@pytest.mark.asyncio
async def test_mock_webhook_404_when_patient_missing(async_client):
    payload = {
        "internal_mock_id": "does_not_exist",
        "date": date.today().isoformat(),
        "duration": 1000,
        "hypnogram": [],
        "avg_hr": 55.0,
        "hrv": 70.0,
        "spo2": 97.0,
    }
    resp = await async_client.post("/api/v1/wearable/mock-webhook", json=payload)
    assert resp.status_code == 404

