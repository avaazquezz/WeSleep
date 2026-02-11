"""
API dependencies.

Common dependencies used across route handlers, such as database sessions.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_maker

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to provide a database session.

    Yields:
        AsyncSession: An asynchronous database session.
    """
    async with async_session_maker() as session:
        yield session
