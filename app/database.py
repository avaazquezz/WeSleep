"""
Database connection and session management.

This module sets up the asynchronous engine and session maker for SQLModel/SQLAlchemy.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel

from app.config import settings

# Crear motor asíncrono para PostgreSQL
engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, echo=True)

async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db() -> None:
    """
    Initialize the database by creating all tables defined in SQLModel metadata.

    This function should be called on application startup.
    """
    async with engine.begin() as conn:
        # En producción usaríamos Alembic, aquí creamos tablas para dev rápido
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to provide a database session.

    Yields:
        AsyncSession: An asynchronous database session.
    """
    async with async_session_maker() as session:
        yield session
