"""
Database connection and session management.

This module sets up the asynchronous engine and session maker for SQLModel/SQLAlchemy.
"""
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.config import settings

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
    """
    Initialize the database by creating all tables defined in SQLModel metadata.

    This function should be called on application startup.
    """
    async with engine.begin() as conn:
        # En producción usaríamos Alembic, aquí creamos tablas para dev rápido
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session():
    """
    Dependency to provide a database session.

    Yields:
        AsyncSession: An asynchronous database session.
    """
    async with async_session_maker() as session:
        yield session
