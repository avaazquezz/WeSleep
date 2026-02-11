"""
API endpoints for Smart Alarm functionality.

Handles requests to predict the optimal wake-up time based on sleep cycles.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.routers.deps import get_session
from app.models import SmartAlarmRequest, SmartAlarmResponse, SleepRecord
import app.logic as logic

router = APIRouter()

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

    # 3. Calculate wakeup window
    prediction = logic.predict_optimal_wakeup(clean_data, request.target_time)
    
    # 4. Calculate sleep quality and anomalies
    quality_score = logic.calculate_sleep_score(clean_data)
    anomalies = logic.detect_sleep_anomalies(clean_data)

    return SmartAlarmResponse(
        suggested_time=prediction.suggested_time,
        confidence=prediction.confidence,
        reasoning=prediction.reasoning,
        quality_score=quality_score,
        anomalies=anomalies
    )
