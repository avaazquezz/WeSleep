from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.core.config import settings

# Crear motor asíncrono para SQLite
# check_same_thread=False es necesario para SQLite
engine = create_async_engine(
    settings.SQLITE_URL, 
    echo=True, 
    connect_args={"check_same_thread": False}
)

async_session_maker = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        # En producción usaríamos Alembic, aquí creamos tablas para dev rápido
        await conn.run_sync(SQLModel.metadata.create_all)
