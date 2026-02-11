from fastapi import FastAPI
from app.config import settings

"""
Main entry point for the WeSleep API application.

This module configures the FastAPI application, includes routers,
and defines the startup events (such as database initialization).
"""
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database import init_db
    """
    Lifespan context manager for the FastAPI application.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Yields control back to the application.
    """
    await init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

from app.routers import api_router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", status_code=200)
async def health_check():
    """
    Health check endpoint to verify service status.
    """
    return {"status": "ok", "project": settings.PROJECT_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
