from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, JSON
from sqlalchemy import Column
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

class RawSleepData(SQLModel, table=True):
    __tablename__ = "raw_sleep_data"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True, nullable=False) # Simulado por ahora, vendría del token
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Metadatos para búsqueda rápida
    provider_source: str = Field(index=True)
    record_id_provider: str = Field(index=True)
    
    # Payload completo
    # En SQLite, JSON se guarda como TEXT, pero SQLModel/SQLAlchemy manejan la serialización
    payload: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
