"""
RootTrace FastAPI Application Entry Point
==========================================
Wires together:
- CORS middleware
- Authentication routes
- Incident routes
- Investigation routes
- Document routes
- Recommendation/approval routes
- Evaluation routes
- Startup events (DB health check)
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, documents, evaluation, incidents, investigations, recommendations
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on application startup and shutdown.
    We verify the database connection here so the app fails loudly
    on startup rather than silently failing on the first request.
    """
    logger.info("roottrace.startup", environment=settings.environment)
    # Verify DB connection
    async with engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    logger.info("roottrace.database.connected")
    yield
    # Shutdown
    await engine.dispose()
    logger.info("roottrace.shutdown")


app = FastAPI(
    title="RootTrace API",
    description="Agentic AI for Evidence-Driven Incident Investigation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────
# Only allow the frontend origin (configurable via env)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route Registration ────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(incidents.router, prefix="/api/incidents", tags=["Incidents"])
app.include_router(investigations.router, prefix="/api/investigations", tags=["Investigations"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])
app.include_router(evaluation.router, prefix="/api/evaluation", tags=["Evaluation"])


@app.get("/api/health", tags=["Health"])
async def health_check():
    """
    Simple liveness probe. Docker and load balancers use this to
    verify the service is running before sending traffic.
    """
    return {"status": "healthy", "service": "roottrace-api", "version": "1.0.0"}
