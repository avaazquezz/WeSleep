from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Patient, SleepRecord, Tenant


def _make_payload(d: date, *, hrv: float, duration_hours: float, bed_hours: float, deep_minutes: int) -> dict:
    start = "23:00"
    end = f"{int(bed_hours):02d}:00"
    # If end <= start, our parser treats it as crossing midnight (adds +1 day)
    hypnogram = [
        {"start_time": start, "end_time": end, "phase": "light"},
        {"start_time": "01:00", "end_time": f"{(1 + deep_minutes // 60):02d}:{deep_minutes % 60:02d}", "phase": "deep"},
    ]
    return {
        "date": d.isoformat(),
        "duration": int(duration_hours * 3600 * 1000),
        "hypnogram": hypnogram,
        "hrv": hrv,
    }


async def _seed_patient(session_maker, internal_mock_id: str = "p1") -> Patient:
    async with session_maker() as session:  # type: AsyncSession
        tenant = Tenant(name="T", api_key="tenant_insights")
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

        patient = Patient(tenant_id=tenant.id, internal_mock_id=internal_mock_id)
        session.add(patient)
        await session.commit()
        await session.refresh(patient)
        return patient


async def _seed_sleep_records(session_maker, patient_id, days: int, *, start_days_ago: int, hrv: float, eff: float) -> None:
    # bed fixed at 8h; duration derived from efficiency
    bed_h = 8.0
    dur_h = bed_h * eff
    today = date.today()
    start_date = today - timedelta(days=start_days_ago)
    async with session_maker() as session:
        for i in range(days):
            d = start_date + timedelta(days=i)
            payload = _make_payload(d, hrv=hrv, duration_hours=dur_h, bed_hours=bed_h, deep_minutes=90)
            session.add(SleepRecord(patient_id=patient_id, date=d, payload=payload))
        await session.commit()


def _mock_groq_return(text: str):
    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )
    mock_client = SimpleNamespace()
    mock_client.chat = SimpleNamespace()
    mock_client.chat.completions = SimpleNamespace()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.mark.asyncio
async def test_weekly_insights_happy_path(async_client, session_maker):
    patient = await _seed_patient(session_maker, internal_mock_id="mock_healthy")
    # 14 days total: first 7 baseline, last 7 current
    await _seed_sleep_records(session_maker, patient.id, 14, start_days_ago=13, hrv=70.0, eff=0.9)

    mock_client = _mock_groq_return("Linea 1\nLinea 2\nLinea 3\nLinea 4")
    with patch("app.services.reasoning_service.AsyncGroq", return_value=mock_client), patch(
        "app.services.reasoning_service.settings"
    ) as ms:
        ms.GROQ_API_KEY = "test-key"
        resp = await async_client.get(f"/api/v1/insights/weekly/{patient.id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["patient_id"] == str(patient.id)
    assert len(data["daily"]) == 14
    assert data["weekly_recap"] == "Linea 1\nLinea 2\nLinea 3"


@pytest.mark.asyncio
async def test_weekly_insights_insufficient_data_400(async_client, session_maker):
    patient = await _seed_patient(session_maker, internal_mock_id="mock_fatigue")
    await _seed_sleep_records(session_maker, patient.id, 5, start_days_ago=4, hrv=60.0, eff=0.9)
    resp = await async_client.get(f"/api/v1/insights/weekly/{patient.id}")
    assert resp.status_code == 400
    assert "Datos insuficientes" in resp.text


@pytest.mark.asyncio
async def test_monthly_insights_returns_alert_when_drop_severe(async_client, session_maker):
    patient = await _seed_patient(session_maker, internal_mock_id="mock_fragmented")
    # 30 days: first 15 high metrics, last 15 low metrics to trigger alert
    await _seed_sleep_records(session_maker, patient.id, 15, start_days_ago=29, hrv=70.0, eff=0.9)
    await _seed_sleep_records(session_maker, patient.id, 15, start_days_ago=14, hrv=50.0, eff=0.7)

    mock_client = _mock_groq_return("ALERTA FORMAL\nL2\nL3\nL4\nL5")
    with patch("app.services.reasoning_service.AsyncGroq", return_value=mock_client), patch(
        "app.services.reasoning_service.settings"
    ) as ms:
        ms.GROQ_API_KEY = "test-key"
        resp = await async_client.get(f"/api/v1/insights/monthly/{patient.id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["alert"] == "ALERTA FORMAL\nL2\nL3\nL4"


@pytest.mark.asyncio
async def test_monthly_insights_no_alert_when_stable(async_client, session_maker):
    patient = await _seed_patient(session_maker, internal_mock_id="mock_stable")
    await _seed_sleep_records(session_maker, patient.id, 30, start_days_ago=29, hrv=70.0, eff=0.9)
    resp = await async_client.get(f"/api/v1/insights/monthly/{patient.id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["alert"] is None

