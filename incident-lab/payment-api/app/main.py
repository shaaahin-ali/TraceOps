"""
payment-api — RootTrace Incident Lab Application
==================================================
A realistic FastAPI payment service used as the investigation target.

This is NOT a commercial application.
Its purpose is to have realistic engineering history with deliberate defects
that the RootTrace agent must discover through evidence investigation.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, get_db
from app.routers import payments, auth, health
from app.logging_config import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("payment_api.startup", version=settings.app_version)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    logger.info("payment_api.shutdown")


app = FastAPI(
    title="Payment API",
    description="Payment processing service — RootTrace Incident Lab",
    version="2.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
