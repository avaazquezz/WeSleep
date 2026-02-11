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
    Ingesta de datos crudos de weareables (ej. Apple HealthKit).
    
    - Valida el payload contra el esquema estricto.
    - Persiste el JSON crudo para auditoría y procesamiento futuro.
    - Retorna el UUID del registro creado internamente.
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
