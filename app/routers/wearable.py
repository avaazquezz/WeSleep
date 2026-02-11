"""
API endpoints for Wearable Data Ingestion.

Handles the reception and storage of raw sleep data from providers like Apple HealthKit.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.routers.deps import get_session
from app.models import WearableRawPayload, SleepRecord

router = APIRouter()

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
        # En un escenario real, user_id vendría del token de autenticación
        # Por ahora generamos uno o usamos uno fijo para pruebas si no hay auth implementado
        dummy_user_id = UUID("00000000-0000-0000-0000-000000000001") 

        # Crear instancia del modelo SQLModel
        sleep_record = SleepRecord(
            user_id=dummy_user_id,
            provider_source=payload.provider_source,
            record_id_provider=str(payload.record_id),
            payload=payload.model_dump(mode='json'),
            timestamp=payload.start_at_timestamp 
        )

        session.add(sleep_record)
        await session.commit()
        await session.refresh(sleep_record)

        return sleep_record.id

    except Exception as e:
        # Loguear el error real aquí
        print(f"Error ingesting data: {e}")
        raise HTTPException(status_code=500, detail="Error interno procesando los datos")
