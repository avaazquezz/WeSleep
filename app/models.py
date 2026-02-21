"""
Database models and Pydantic schemas for WeSleep.

Defines the structure for Sleep Records, Smart Alarm requests, and internal data formats.
"""
from datetime import date as date_type
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4
from enum import Enum

from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, JSON
from sqlalchemy.dialects.postgresql import JSONB
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
    source_version: str | None = Field(
        None, description="Versión del SO o App fuente"
    )
    source_bundle_identifier: str | None = Field(
        None, description="Identificador del bundle de la App fuente"
    )
    model_config = ConfigDict(extra="allow")

class WearableMetrics(BaseModel):
    """
    Sub-documento con las métricas detalladas del sueño.
    """
    heartrate_max: int | None = Field(None, description="Frecuencia cardíaca máxima")
    heartrate_min: int | None = Field(None, description="Frecuencia cardíaca mínima")
    heartrate: float | None = Field(None, description="Frecuencia cardíaca promedio")
    hrv_sdnn: float | None = Field(
        None, description="Variabilidad de la frecuencia cardíaca (SDNN)"
    )
    spo2: float | None = Field(None, description="Saturación de oxígeno promedio")
    spo2_max: float | None = Field(None, description="Saturación de oxígeno máxima")
    spo2_min: float | None = Field(None, description="Saturación de oxígeno mínima")
    sleep_duration: int | None = Field(
        None, description="Duración total del sueño en milisegundos"
    )
    sleep_duration_deep: int | None = Field(None, description="Duración sueño profundo en ms")
    sleep_duration_light: int | None = Field(None, description="Duración sueño ligero en ms")
    sleep_duration_rem: int | None = Field(None, description="Duración sueño REM en ms")
    sleep_duration_awake: int | None = Field(None, description="Duración despierto en ms")
    bedtime_duration: int | None = Field(None, description="Tiempo total en cama en ms")
    sleep_interruptions: int | None = Field(None, description="Número de interrupciones")
    sleep_breathing_rate: float | None = Field(
        None, description="Frecuencia respiratoria promedio"
    )
    sleep_breathing_rate_min: float | None = Field(
        None, description="Frecuencia respiratoria mínima"
    )
    sleep_breathing_rate_max: float | None = Field(
        None, description="Frecuencia respiratoria máxima"
    )
    skin_temperature: float | None = Field(
        None, description="Temperatura de la piel promedio"
    )
    skin_temperature_max: float | None = Field(
        None, description="Temperatura de la piel máxima"
    )
    skin_temperature_min: float | None = Field(
        None, description="Temperatura de la piel mínima"
    )
    model_config = ConfigDict(extra="allow")

class WearableRawPayload(BaseModel):
    """
    Payload crudo recibido del proveedor.
    """
    record_id: UUID = Field(..., description="Identificador único del registro en el proveedor")
    modified_at: datetime = Field(..., description="Timestamp de última modificación")
    start_at_timestamp: datetime = Field(..., description="Inicio del periodo de sueño")
    end_at_timestamp: datetime = Field(..., description="Fin del periodo de sueño")
    duration: int = Field(..., description="Duración total en milisegundos")
    user_time_offset_minutes: int | None = Field(
        None, description="Offset de zona horaria en minutos"
    )
    input_method: str | None = Field(
        None, description="Método de entrada (e.g., device)"
    )
    
    metrics: WearableMetrics = Field(..., description="Métricas de salud detalladas")
    
    provider_source: str = Field(..., description="Fuente del proveedor (e.g., apple_healthkit_sleep_aggregation)")
    provider_source_type: str | None = Field(
        None, description="Tipo de fuente (e.g., activity)"
    )
    provider_slug: str = Field(..., description="Slug del proveedor (e.g., apple)")
    
    source: WearableSource | None = Field(None, description="Detalles técnicos de la fuente")
    
    sleep_id: UUID | None = Field(None, description="ID asociado al sueño, si existe")
    score: int | None = Field(None, description="Puntuación de sueño calculada por el proveedor")

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
    media_HR: float | None = Field(None, description="Frecuencia cardíaca media")
    var_HR: float | None = Field(
        None, description="Varianza de FC (o HRV SDNN como proxy)"
    )
    HRV: float | None = Field(
        None, description="Variabilidad de la frecuencia cardíaca (SDNN)"
    )
    
    # Oxigenación
    SpO2: float | None = Field(None, description="SpO2 promedio")
    SpO2_min: float | None = Field(None, description="SpO2 mínimo")
    SpO2_max: float | None = Field(None, description="SpO2 máximo")
    
    # Movimiento y Respiración
    movimiento: float | None = Field(
        None, description="Índice de movimiento normalizado (0-1)"
    )
    breathing_rate: float | None = Field(
        None, description="Frecuencia respiratoria media"
    )
    
    # Fases del Sueño
    sleep_duration_deep: int = Field(0, description="Duración sueño profundo en ms")
    sleep_duration_light: int = Field(0, description="Duración sueño ligero en ms")
    sleep_duration_rem: int = Field(0, description="Duración sueño REM en ms")
    sleep_duration_awake: int = Field(0, description="Duración despierto en ms")

    # Time Series (Hypnogram)
    hypnogram: list[SleepSegment] = Field(
        default_factory=list, description="Secuencia de fases de sueño"
    )

    model_config = ConfigDict(extra="ignore")


# --- Database Models ---

class Tenant(SQLModel, table=True):
    """
    Database model representing a Health Mutual (Mutua de salud) or B2B client.
    """
    __tablename__ = "tenants"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(nullable=False, index=True)
    api_key: str = Field(nullable=False, unique=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    patients: List["Patient"] = Relationship(
        back_populates="tenant",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )


class Patient(SQLModel, table=True):
    """
    Database model representing an end-user (patient) belonging to a Tenant.
    """
    __tablename__ = "patients"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(
        foreign_key="tenants.id",
        nullable=False,
        index=True,
    )
    internal_mock_id: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="ID for synthetic data association",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    tenant: Optional["Tenant"] = Relationship(
        back_populates="patients",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    sleep_records: List["SleepRecord"] = Relationship(
        back_populates="patient",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
            "passive_deletes": True,
        },
    )


class SleepRecord(SQLModel, table=True):
    """
    Database model for storing raw sleep data for a specific night.
    """
    __tablename__ = "sleep_records"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    patient_id: UUID = Field(
        foreign_key="patients.id",
        nullable=False,
        index=True,
    )
    date: date_type = Field(index=True, description="The date of the sleep night")
    
    # Payload completo
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql"), nullable=False),
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    patient: Optional["Patient"] = Relationship(
        back_populates="sleep_records",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# --- API Request/Response Models ---

class WakeupPrediction(BaseModel):
    """
    Model representing the result of a smart alarm prediction.
    """
    suggested_time: datetime
    confidence: float
    reasoning: str

class SmartAlarmRequest(BaseModel):
    """
    Request payload for the smart alarm endpoint.
    """
    sleep_record_id: UUID = Field(..., description="ID del registro de sueño a analizar")
    target_time: datetime = Field(..., description="Hora objetivo para despertar")

class SmartAlarmResponse(WakeupPrediction):
    """
    Response payload for the smart alarm endpoint, including quality score.
    """
    quality_score: float = Field(..., description="Puntuación de calidad del sueño (0-100)")
    anomalies: list[str] = Field(
        default_factory=list, description="Lista de anomalías detectadas"
    )
