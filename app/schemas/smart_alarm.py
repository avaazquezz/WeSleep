from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.core.strategies import WakeupPrediction

class SmartAlarmRequest(BaseModel):
    sleep_record_id: UUID = Field(..., description="ID del registro de sueño a analizar")
    target_time: datetime = Field(..., description="Hora objetivo para despertar")

class SmartAlarmResponse(WakeupPrediction):
    quality_score: float = Field(..., description="Puntuación de calidad del sueño (0-100)")
    anomalies: list[str] = Field(default_factory=list, description="Lista de anomalías detectadas")
