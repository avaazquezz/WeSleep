from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.api.deps import get_db, get_smart_alarm_strategy
from app.schemas.smart_alarm import SmartAlarmRequest, SmartAlarmResponse
from app.core.strategies import SmartAlarmStrategy
from app.models.raw_data import RawSleepData
from app.services.parser import SleepDataParser

router = APIRouter()

@router.post("/smart-alarm", response_model=SmartAlarmResponse)
async def predict_smart_alarm(
    request: SmartAlarmRequest,
    db: AsyncSession = Depends(get_db),
    strategy: SmartAlarmStrategy = Depends(get_smart_alarm_strategy)
):
    """
    Calcula la hora óptima para despertar basada en el ID del registro de sueño.
    """
    # 1. Fetch raw data
    result = await db.exec(select(RawSleepData).where(RawSleepData.id == request.sleep_record_id))
    raw_record = result.first()
    
    if not raw_record:
        raise HTTPException(status_code=404, detail="Sleep record not found")

    # 2. Parse data to CleanSleepData
    # Asumimos que raw_record.payload es un dict compatible
    try:
        clean_data = SleepDataParser.parse_payload(raw_record.payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing sleep data: {str(e)}")

    # 3. Calculate wakeup window
    prediction = strategy.calculate_wakeup_window(clean_data, request.target_time)
    
    # 4. Calculate sleep quality and anomalies
    from app.services.evaluator import SleepEvaluator
    evaluator = SleepEvaluator()
    quality_score = evaluator.calculate_score(clean_data)
    anomalies = evaluator.detect_anomalies(clean_data)

    return SmartAlarmResponse(
        suggested_time=prediction.suggested_time,
        confidence=prediction.confidence,
        reasoning=prediction.reasoning,
        quality_score=quality_score,
        anomalies=anomalies
    )
