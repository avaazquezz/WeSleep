from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import async_session_maker
from app.core.strategies import SmartAlarmStrategy
from app.services.smart_alarm import HeuristicAlarmStrategy

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

def get_smart_alarm_strategy() -> SmartAlarmStrategy:
    return HeuristicAlarmStrategy()

