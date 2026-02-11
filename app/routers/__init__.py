from fastapi import APIRouter
from app.routers import wearable, alarm

api_router = APIRouter()

# Webhooks de wearables (Apple HealthKit)
api_router.include_router(wearable.router, prefix="/webhooks/wearable", tags=["wearables"])
api_router.include_router(alarm.router, prefix="/sleep", tags=["sleep"])
