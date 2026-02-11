from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.schemas.wearable import WearableRawPayload
from app.models.raw_data import RawSleepData

router = APIRouter()

@router.post("/", response_model=UUID, status_code=200)
async def ingest_wearable_data(
    payload: WearableRawPayload,
    db: AsyncSession = Depends(get_db),
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
        # Asumiremos un user_id hardcodeado para la prueba técnica si no hay auth
        dummy_user_id = UUID("00000000-0000-0000-0000-000000000001") 

        raw_entry = RawSleepData(
            user_id=dummy_user_id,
            provider_source=payload.provider_source,
            record_id_provider=str(payload.record_id),
            payload=payload.model_dump(mode='json'),
            timestamp=payload.start_at_timestamp # Usamos el inicio del sueño como timestamp principal
        )

        db.add(raw_entry)
        await db.commit()
        await db.refresh(raw_entry)

        return raw_entry.id

    except Exception as e:
        # Loguear el error real aquí
        print(f"Error ingesting data: {e}")
        raise HTTPException(status_code=500, detail="Error interno procesando los datos")
