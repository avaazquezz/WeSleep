"""
API endpoints for Smart Alarm functionality.

Handles requests to predict the optimal wake-up time based on sleep cycles.
"""
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.routers.deps import get_session
from app.models import SmartAlarmRequest, SmartAlarmResponse, SleepRecord
import app.logic as logic

router = APIRouter()
alarm_router = APIRouter()

@router.post("/smart-alarm", response_model=SmartAlarmResponse)
async def predict_smart_alarm(
    request: SmartAlarmRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Predict optimal wake-up time.

    Analyzes a specific Sleep Record to find the best time to wake up within
    a 30-minute window before the target time.

    Args:
        request (SmartAlarmRequest): Target time and Sleep Record ID.
        session (AsyncSession): Database session.

    Returns:
        SmartAlarmResponse: Suggested time, confidence, and sleep analysis.

    Raises:
        HTTPException(404): If the sleep record is not found.
        HTTPException(500): If there is an error parsing the data.
    """
    # 1. Fetch raw data
    # SQLModel select style
    statement = select(SleepRecord).where(SleepRecord.id == request.sleep_record_id)
    result = await session.exec(statement)
    record = result.first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Sleep record not found")

    # 2. Parse data to CleanSleepData
    try:
        clean_data = logic.parse_sleep_payload(record.payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing sleep data: {str(e)}")

    # 3. Calculate sleep quality and anomalies (needed by Gemini reasoning)
    quality_score = logic.calculate_sleep_score(clean_data)
    anomalies = logic.detect_sleep_anomalies(clean_data)

    # 4. Calculate wakeup window (async — calls Gemini for personalized reasoning)
    prediction = await logic.predict_optimal_wakeup(
        clean_data,
        request.target_time,
        quality_score=quality_score,
        anomalies=anomalies,
    )

    return SmartAlarmResponse(
        suggested_time=prediction.suggested_time,
        confidence=prediction.confidence,
        reasoning=prediction.reasoning,
        quality_score=quality_score,
        anomalies=anomalies
    )


@alarm_router.get("/predict/{patient_id}", status_code=200)
async def predict_optimal_alarm_time(
    patient_id: UUID,
    target_time: str = Query(..., description="Target time in HH:MM format (e.g. 07:30)"),
    session: AsyncSession = Depends(get_session),
):
    since = date.today() - timedelta(days=6)
    statement = (
        select(SleepRecord)
        .where(SleepRecord.patient_id == patient_id, SleepRecord.date >= since)
        .order_by(SleepRecord.date.desc())
    )
    result = await session.exec(statement)
    records = result.all()

    historical_payloads: list[dict] = []
    for r in records:
        if isinstance(r.payload, dict):
            historical_payloads.append(r.payload)

    optimal = logic.calculate_optimal_wakeup_time(
        historical_records=historical_payloads,
        target_time_str=target_time,
        window_minutes=30,
    )

    nights = min(7, len(historical_payloads))
    reason = (
        f"Basado en {nights} noches históricas (últimos 7 días) y puntuación por fases minuto a minuto."
        if nights > 0
        else "Datos insuficientes para estimar una mejor hora; se devuelve la hora objetivo."
    )

    return {
        "patient_id": str(patient_id),
        "target_time": target_time,
        "optimal_wakeup_time": optimal,
        "reason": reason,
    }
