from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from enum import Enum

from sqlmodel import Field, SQLModel, JSON
from sqlalchemy import Column
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from pydantic import BaseModel, ConfigDict


# --- Enums & Auxiliary Models ---

class SleepPhase(str, Enum):
    DEEP = "deep"
    LIGHT = "light"
    REM = "rem"
    AWAKE = "awake"

class SleepSegment(BaseModel):
    start_at: datetime
    end_at: datetime
    phase: SleepPhase

class WearableSource(BaseModel):
    """
    Información sobre la fuente de los datos (dispositivo, versión).
    """
    source_version: Optional[str] = Field(None, description="Versión del SO o App fuente")
    source_bundle_identifier: Optional[str] = Field(None, description="Identificador del bundle de la App fuente")
    model_config = ConfigDict(extra="allow")

class WearableMetrics(BaseModel):
    """
    Sub-documento con las métricas detalladas del sueño.
    """
    heartrate_max: Optional[int] = Field(None, description="Frecuencia cardíaca máxima")
    heartrate_min: Optional[int] = Field(None, description="Frecuencia cardíaca mínima")
    heartrate: Optional[float] = Field(None, description="Frecuencia cardíaca promedio")
    hrv_sdnn: Optional[float] = Field(None, description="Variabilidad de la frecuencia cardíaca (SDNN)")
    spo2: Optional[float] = Field(None, description="Saturación de oxígeno promedio")
    spo2_max: Optional[float] = Field(None, description="Saturación de oxígeno máxima")
    spo2_min: Optional[float] = Field(None, description="Saturación de oxígeno mínima")
    sleep_duration: Optional[int] = Field(None, description="Duración total del sueño en milisegundos")
    sleep_duration_deep: Optional[int] = Field(None, description="Duración sueño profundo en ms")
    sleep_duration_light: Optional[int] = Field(None, description="Duración sueño ligero en ms")
    sleep_duration_rem: Optional[int] = Field(None, description="Duración sueño REM en ms")
    sleep_duration_awake: Optional[int] = Field(None, description="Duración despierto en ms")
    bedtime_duration: Optional[int] = Field(None, description="Tiempo total en cama en ms")
    sleep_interruptions: Optional[int] = Field(None, description="Número de interrupciones")
    sleep_breathing_rate: Optional[float] = Field(None, description="Frecuencia respiratoria promedio")
    sleep_breathing_rate_min: Optional[float] = Field(None, description="Frecuencia respiratoria mínima")
    sleep_breathing_rate_max: Optional[float] = Field(None, description="Frecuencia respiratoria máxima")
    skin_temperature: Optional[float] = Field(None, description="Temperatura de la piel promedio")
    skin_temperature_max: Optional[float] = Field(None, description="Temperatura de la piel máxima")
    skin_temperature_min: Optional[float] = Field(None, description="Temperatura de la piel mínima")
    model_config = ConfigDict(extra="allow")

class WearableRawPayload(BaseModel):
    """
    Payload crudo recibido del proveedor (Apple HealthKit).
    """
    record_id: UUID = Field(..., description="Identificador único del registro en el proveedor")
    modified_at: datetime = Field(..., description="Timestamp de última modificación")
    start_at_timestamp: datetime = Field(..., description="Inicio del periodo de sueño")
    end_at_timestamp: datetime = Field(..., description="Fin del periodo de sueño")
    duration: int = Field(..., description="Duración total en milisegundos")
    user_time_offset_minutes: Optional[int] = Field(None, description="Offset de zona horaria en minutos")
    input_method: Optional[str] = Field(None, description="Método de entrada (e.g., device)")
    
    metrics: WearableMetrics = Field(..., description="Métricas de salud detalladas")
    
    provider_source: str = Field(..., description="Fuente del proveedor (e.g., apple_healthkit_sleep_aggregation)")
    provider_source_type: Optional[str] = Field(None, description="Tipo de fuente (e.g., activity)")
    provider_slug: str = Field(..., description="Slug del proveedor (e.g., apple)")
    
    source: Optional[WearableSource] = Field(None, description="Detalles técnicos de la fuente")
    
    sleep_id: Optional[UUID] = Field(None, description="ID asociado al sueño, si existe")
    score: Optional[int] = Field(None, description="Puntuación de sueño calculada por el proveedor")

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "record_id": "0134ff3c-3f60-8c46-8e4e-c0dd218c4e3a",
                "modified_at": "2025-04-30T12:00:26Z",
                "start_at_timestamp": "2025-04-28T17:30:00Z",
                "end_at_timestamp": "2025-04-29T03:34:00Z",
                "duration": 36240000,
                "metrics": {
                    "heartrate": 56,
                    "sleep_duration": 25920000
                },
                "provider_source": "apple_healthkit_sleep_aggregation",
                "provider_slug": "apple"
            }
        }
    )

class CleanSleepData(BaseModel):
    """
    Formato interno optimizado y normalizado de datos de sueño.
    """
    start_at_timestamp: datetime = Field(..., description="Inicio del periodo de sueño")
    end_at_timestamp: datetime = Field(..., description="Fin del periodo de sueño")
    duration: int = Field(..., description="Duración total en milisegundos")
    
    # Métricas Cardíacas
    media_HR: Optional[float] = Field(None, description="Frecuencia cardíaca media")
    var_HR: Optional[float] = Field(None, description="Varianza de FC (o HRV SDNN como proxy)")
    HRV: Optional[float] = Field(None, description="Variabilidad de la frecuencia cardíaca (SDNN)")
    
    # Oxigenación
    SpO2: Optional[float] = Field(None, description="SpO2 promedio")
    SpO2_min: Optional[float] = Field(None, description="SpO2 mínimo")
    SpO2_max: Optional[float] = Field(None, description="SpO2 máximo")
    
    # Movimiento y Respiración
    movimiento: Optional[float] = Field(None, description="Índice de movimiento normalizado (0-1)")
    breathing_rate: Optional[float] = Field(None, description="Frecuencia respiratoria media")
    
    # Fases del Sueño
    sleep_duration_deep: int = Field(0, description="Duración sueño profundo en ms")
    sleep_duration_light: int = Field(0, description="Duración sueño ligero en ms")
    sleep_duration_rem: int = Field(0, description="Duración sueño REM en ms")
    sleep_duration_awake: int = Field(0, description="Duración despierto en ms")

    # Time Series (Hypnogram)
    hypnogram: List[SleepSegment] = Field(default_factory=list, description="Secuencia de fases de sueño")

    model_config = ConfigDict(extra="ignore")


# --- Database Models ---

class SleepRecord(SQLModel, table=True):
    __tablename__ = "sleep_records"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True, nullable=False) # Simulado por ahora, vendría del token
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Metadatos para búsqueda rápida
    provider_source: str = Field(index=True)
    record_id_provider: str = Field(index=True)
    
    # Payload completo
    payload: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- API Request/Response Models ---

class WakeupPrediction(BaseModel):
    suggested_time: datetime
    confidence: float
    reasoning: str

class SmartAlarmRequest(BaseModel):
    sleep_record_id: UUID = Field(..., description="ID del registro de sueño a analizar")
    target_time: datetime = Field(..., description="Hora objetivo para despertar")

class SmartAlarmResponse(WakeupPrediction):
    quality_score: float = Field(..., description="Puntuación de calidad del sueño (0-100)")
    anomalies: List[str] = Field(default_factory=list, description="Lista de anomalías detectadas")
