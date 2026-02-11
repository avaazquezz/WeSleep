from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.core.strategies import WakeupPrediction

class SmartAlarmRequest(BaseModel):
    sleep_record_id: UUID = Field(..., description="ID del registro de sueño a analizar")
    target_time: datetime = Field(..., description="Hora objetivo para despertar")

class SmartAlarmResponse(WakeupPrediction):
    pass
