from fastapi import APIRouter
from app.routers import alarm, insights, wearable

api_router = APIRouter()

# Webhooks de wearables 
api_router.include_router(wearable.router, prefix="/webhooks/wearable", tags=["wearables"])
api_router.include_router(wearable.router, prefix="/wearable", tags=["wearables"])
api_router.include_router(alarm.router, prefix="/sleep", tags=["sleep"])
api_router.include_router(alarm.alarm_router, prefix="/alarm", tags=["alarm"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
