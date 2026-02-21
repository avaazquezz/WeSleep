"""
API endpoints for Wearable Data Ingestion.

Handles the reception and storage of raw sleep data from providers like Apple HealthKit.
"""
from __future__ import annotations

from datetime import date as date_type
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.routers.deps import get_session
from app.models import Patient, SleepRecord, Tenant, WearableRawPayload

router = APIRouter()


class MockWebhookPayload(BaseModel):
    internal_mock_id: str = Field(..., min_length=1)
    date: date_type
    duration: int = Field(..., ge=0)
    hypnogram: list[dict[str, Any]] = Field(default_factory=list)
    avg_hr: float | None = None
    hrv: float | None = None
    spo2: float | None = None


async def _get_or_create_default_tenant(session: AsyncSession) -> Tenant:
    api_key = "dev_default_tenant"
    result = await session.exec(select(Tenant).where(Tenant.api_key == api_key))
    tenant = result.first()
    if tenant is not None:
        return tenant

    tenant = Tenant(name="Default Tenant (dev)", api_key=api_key)
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return tenant


@router.post("/", response_model=UUID, status_code=200)
async def ingest_wearable_data(
    payload: WearableRawPayload,
    session: AsyncSession = Depends(get_session),
    # user_id: UUID = Depends(get_current_user_id) # TODO: Implementar Auth
) -> UUID:
    """
    Ingest raw wearable data.

    Receives a raw JSON payload (e.g., from Apple HealthKit), validates it against
    the strict `WearableRawPayload` schema, and persists it in the database.

    Args:
        payload (WearableRawPayload): The raw data to ingest.
        session (AsyncSession): Database session.

    Returns:
        UUID: The internal ID of the created SleepRecord.

    Raises:
        HTTPException(500): If there is an internal processing error.
    """
    try:
        tenant = await _get_or_create_default_tenant(session)
        internal_mock_id = f"wearable_{payload.record_id}"

        result = await session.exec(
            select(Patient).where(Patient.internal_mock_id == internal_mock_id)
        )
        patient = result.first()
        if patient is None:
            patient = Patient(tenant_id=tenant.id, internal_mock_id=internal_mock_id)
            session.add(patient)
            await session.commit()
            await session.refresh(patient)

        sleep_record = SleepRecord(
            patient_id=patient.id,
            date=payload.start_at_timestamp.date(),
            payload=payload.model_dump(mode="json"),
        )

        session.add(sleep_record)
        await session.commit()
        await session.refresh(sleep_record)

        return sleep_record.id

    except Exception as e:
        # Loguear el error real aquí
        print(f"Error ingesting data: {e}")
        raise HTTPException(status_code=500, detail="Error interno procesando los datos")


@router.post("/mock-webhook", response_model=UUID, status_code=200)
async def ingest_mock_webhook(
    payload: MockWebhookPayload,
    session: AsyncSession = Depends(get_session),
) -> UUID:
    result = await session.exec(
        select(Patient).where(Patient.internal_mock_id == payload.internal_mock_id)
    )
    patient = result.first()
    if patient is None:
        raise HTTPException(
            status_code=404,
            detail=f"Patient not found for internal_mock_id='{payload.internal_mock_id}'",
        )

    sleep_record = SleepRecord(
        patient_id=patient.id,
        date=payload.date,
        payload=payload.model_dump(mode="json"),
    )
    session.add(sleep_record)
    await session.commit()
    await session.refresh(sleep_record)
    return sleep_record.id
