"""
RootTrace Database Layer
========================
Async SQLAlchemy engine + session factory.

Key design decisions:
- async engine (asyncpg) for non-blocking I/O — FastAPI is async-first
- Session factory via AsyncSessionLocal
- get_db() as a FastAPI dependency — yields a session, always closes it
- Base declarative base shared by all models
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────
# pool_size / max_overflow control how many DB connections exist.
# For the incident lab, moderate values are fine.
engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,     # verifies connection before use
    echo=(settings.environment == "development"),
)

# ── Session Factory ───────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,  # avoids lazy-load errors after commit in async context
    class_=AsyncSession,
)


# ── Declarative Base ──────────────────────────────────────────
class Base(DeclarativeBase):
    """All SQLAlchemy models inherit from this."""
    pass


# ── FastAPI Dependency ────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a database session for a single request.
    The 'async with' pattern ensures the session is always closed,
    even if an exception is raised during the request.

    Usage in routes:
        @router.get("/...")
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
