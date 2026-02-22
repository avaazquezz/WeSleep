from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

cors_origins = [
    origin.strip()
    for origin in (settings.BACKEND_CORS_ORIGINS or "").split(",")
    if origin.strip()
]

cors_allow_all = any(o == "*" for o in cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if cors_allow_all else cors_origins,
    allow_origin_regex=None
    if cors_allow_all
    else r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|(?:10|192\.168)\.\d+\.\d+\.\d+|(?:172\.(?:1[6-9]|2\d|3[0-1]))\.\d+\.\d+)(?::\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
