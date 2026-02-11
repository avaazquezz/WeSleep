from fastapi import APIRouter
from app.api.v1.endpoints import wearable

api_router = APIRouter()

# Webhooks de wearables (Apple HealthKit)
api_router.include_router(wearable.router, prefix="/webhooks/wearable", tags=["wearables"])
