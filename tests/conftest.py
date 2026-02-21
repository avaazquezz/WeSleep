from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_maker(
    test_engine: AsyncEngine,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    yield maker


@pytest_asyncio.fixture(autouse=True)
async def _patch_app_db(
    test_engine: AsyncEngine,
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[None, None]:
    from app.main import app
    import app.database as database
    import app.routers.deps as deps

    database.engine = test_engine  # type: ignore[assignment]
    database.async_session_maker = session_maker
    deps.async_session_maker = session_maker

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[deps.get_session] = override_get_session
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

