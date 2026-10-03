"""
RootTrace Incident Lab — Git History Builder
=============================================
Creates a realistic Git repository for payment-api with 35+ meaningful commits
including 5 deliberate defect commits for investigation scenarios INC-001 to INC-005.

🎓 HOW THIS WORKS:
We create the git history programmatically using GitPython.
Each commit introduces a real code change — we don't fake them.
The defect commits look like legitimate engineering work
(e.g., "Improve database connection handling") but introduce
subtle bugs that cause realistic production incidents.

GROUND TRUTH (never shown to the AI):
- INC-001: db connection pool size set to None (exhaustion)
- INC-002: N+1 query introduced in payment history retrieval  
- INC-003: unbounded in-memory cache (memory leak)
- INC-004: missing timeout on external fraud-service call
- INC-005: JWT algorithm changed from HS256 to 'none' accidentally

Run this script ONCE to initialize the incident lab.
"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone


REPO_ROOT = Path(__file__).parent.parent / "incident-lab" / "payment-api"
BASE_TIME = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)


def run_git(args: list[str], cwd: Path, env: dict = None):
    """Run a git command safely (no shell=True, no interpolation)."""
    full_env = os.environ.copy()
    full_env.update({
        "GIT_AUTHOR_NAME": "payment-team",
        "GIT_AUTHOR_EMAIL": "team@example.com",
        "GIT_COMMITTER_NAME": "payment-team",
        "GIT_COMMITTER_EMAIL": "team@example.com",
    })
    if env:
        full_env.update(env)
    result = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        env=full_env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Git error: {result.stderr}")
        raise RuntimeError(f"git {' '.join(args)} failed")
    return result.stdout.strip()


def commit(repo: Path, message: str, time_offset_days: float, files_written: list[tuple[Path, str]]):
    """Write files and create a git commit."""
    for path, content in files_written:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        run_git(["add", str(path.relative_to(repo))], repo)

    commit_time = BASE_TIME + timedelta(days=time_offset_days)
    time_str = commit_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    env = {
        "GIT_AUTHOR_DATE": time_str,
        "GIT_COMMITTER_DATE": time_str,
    }
    run_git(["commit", "-m", message], repo, env=env)
    sha = run_git(["rev-parse", "--short", "HEAD"], repo)
    print(f"  [{sha}] {message}")
    return sha


def build_history():
    """Build the complete git history for payment-api."""
    print(f"\n[BUILD] Building incident lab repository at: {REPO_ROOT}\n")
    REPO_ROOT.mkdir(parents=True, exist_ok=True)

    # Initialize repo
    if not (REPO_ROOT / ".git").exists():
        run_git(["init"], REPO_ROOT)
        run_git(["checkout", "-b", "main"], REPO_ROOT)

    shas = {}

    # ── COMMIT 1: Initial project setup ────────────────────────
    shas["c01"] = commit(REPO_ROOT, "Initial FastAPI application", 0, [
        (REPO_ROOT / "README.md", """# payment-api

Payment processing service for RootTrace Incident Lab.

## Endpoints
- POST /payments
- GET  /payments/{id}
- GET  /payments
- GET  /health
"""),
        (REPO_ROOT / "requirements.txt", """fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
sqlalchemy==2.0.35
asyncpg==0.29.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
structlog==24.4.0
httpx==0.27.2
pytest==8.3.3
pytest-asyncio==0.24.0
"""),
        (REPO_ROOT / "app" / "__init__.py", ""),
        (REPO_ROOT / "app" / "main.py", """from fastapi import FastAPI

app = FastAPI(title=\"Payment API\", version=\"1.0.0\")

@app.get(\"/health\")
async def health():
    return {\"status\": \"ok\"}
"""),
    ])

    # ── COMMIT 2: Add config ─────────────────────────────────────
    shas["c02"] = commit(REPO_ROOT, "Add configuration management", 1, [
        (REPO_ROOT / "app" / "config.py", """from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_version: str = \"1.0.0\"
    database_url: str = \"postgresql+asyncpg://payments:payments@localhost/payments\"
    jwt_secret: str = \"dev-secret\"
    jwt_algorithm: str = \"HS256\"
    jwt_expire_minutes: int = 30
    fraud_service_url: str = \"http://fraud-service:8001\"
    fraud_service_timeout: float = 5.0
    db_pool_size: int = 10
    db_max_overflow: int = 20

settings = Settings()
"""),
    ])

    # ── COMMIT 3: Add database layer ─────────────────────────────
    shas["c03"] = commit(REPO_ROOT, "Add PostgreSQL integration", 2, [
        (REPO_ROOT / "app" / "database.py", """from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from collections.abc import AsyncGenerator
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
"""),
    ])

    # ── COMMIT 4: Add payment model ────────────────────────────────
    shas["c04"] = commit(REPO_ROOT, "Add payment model", 3, [
        (REPO_ROOT / "app" / "models.py", """import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum

class PaymentStatus(str, enum.Enum):
    PENDING = \"pending\"
    PROCESSING = \"processing\"
    COMPLETED = \"completed\"
    FAILED = \"failed\"

class Payment(Base):
    __tablename__ = \"payments\"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default=\"USD\")
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class User(Base):
    __tablename__ = \"users\"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
"""),
    ])

    # ── COMMIT 5: Add schemas ──────────────────────────────────────
    shas["c05"] = commit(REPO_ROOT, "Add request/response schemas", 4, [
        (REPO_ROOT / "app" / "schemas.py", """from pydantic import BaseModel, field_validator
from decimal import Decimal
from datetime import datetime
from typing import Optional
from app.models import PaymentStatus

class PaymentCreate(BaseModel):
    user_id: str
    amount: Decimal
    currency: str = \"USD\"
    description: Optional[str] = None

    @field_validator(\"amount\")
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError(\"Amount must be positive\")
        return v

    @field_validator(\"currency\")
    @classmethod
    def currency_must_be_valid(cls, v):
        if v not in {\"USD\", \"EUR\", \"GBP\"}:
            raise ValueError(f\"Unsupported currency: {v}\")
        return v

class PaymentResponse(BaseModel):
    id: str
    user_id: str
    amount: Decimal
    currency: str
    status: PaymentStatus
    description: Optional[str]
    created_at: datetime
    model_config = {\"from_attributes\": True}

class UserCreate(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = \"bearer\"
"""),
    ])

    # ── COMMIT 6: Add structured logging ─────────────────────────
    shas["c06"] = commit(REPO_ROOT, "Add structured logging", 5, [
        (REPO_ROOT / "app" / "logging_config.py", """import structlog
import logging
import sys

def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt=\"iso\"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
"""),
    ])

    # ── COMMIT 7: Add authentication ────────────────────────────
    shas["c07"] = commit(REPO_ROOT, "Add authentication middleware", 7, [
        (REPO_ROOT / "app" / "auth.py", """from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.config import settings

pwd_context = CryptContext(schemes=[\"bcrypt\"], deprecated=\"auto\")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=\"/auth/login\")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode[\"exp\"] = expire
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get(\"sub\")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=\"Invalid token\")
        return {\"user_id\": user_id}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=\"Invalid token\")
"""),
        (REPO_ROOT / "app" / "routers" / "__init__.py", ""),
        (REPO_ROOT / "app" / "routers" / "auth.py", """from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, TokenResponse
from app.auth import hash_password, verify_password, create_access_token

router = APIRouter()
logger = structlog.get_logger(__name__)

@router.post(\"/register\", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=\"Email already registered\")
    user = User(email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({\"sub\": user.id})
    logger.info(\"user.registered\", user_id=user.id)
    return TokenResponse(access_token=token)

@router.post(\"/login\", response_model=TokenResponse)
async def login(data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail=\"Invalid credentials\")
    token = create_access_token({\"sub\": user.id})
    logger.info(\"user.login\", user_id=user.id)
    return TokenResponse(access_token=token)
"""),
    ])

    # ── COMMIT 8: Add health endpoint ──────────────────────────
    shas["c08"] = commit(REPO_ROOT, "Add health endpoint", 9, [
        (REPO_ROOT / "app" / "routers" / "health.py", """from fastapi import APIRouter
from app.config import settings

router = APIRouter()

@router.get(\"/health\")
async def health_check():
    return {
        \"status\": \"healthy\",
        \"service\": \"payment-api\",
        \"version\": settings.app_version,
    }
"""),
    ])

    # ── COMMIT 9: Add payment repository ──────────────────────────
    shas["c09"] = commit(REPO_ROOT, "Add payment repository", 11, [
        (REPO_ROOT / "app" / "repository.py", """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import Payment, PaymentStatus
from app.schemas import PaymentCreate
import structlog

logger = structlog.get_logger(__name__)

class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: PaymentCreate) -> Payment:
        payment = Payment(**data.model_dump())
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def get_by_id(self, payment_id: str) -> Payment | None:
        result = await self.db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[Payment]:
        result = await self.db.execute(
            select(Payment).order_by(Payment.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_user(self, user_id: str) -> list[Payment]:
        result = await self.db.execute(
            select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
        )
        return list(result.scalars().all())
"""),
    ])

    # ── COMMIT 10: Add fraud service client ───────────────────────
    shas["c10"] = commit(REPO_ROOT, "Add external fraud service integration", 13, [
        (REPO_ROOT / "app" / "fraud_service.py", """import httpx
import structlog
from app.config import settings

logger = structlog.get_logger(__name__)

class FraudServiceClient:
    \"\"\"
    Client for the external fraud detection service.
    Uses a configurable timeout to prevent cascading failures.
    \"\"\"

    def __init__(self):
        self.base_url = settings.fraud_service_url
        self.timeout = settings.fraud_service_timeout

    async def check_payment(self, payment_id: str, amount: float, user_id: str) -> dict:
        \"\"\"
        Returns fraud risk assessment.
        Falls back to 'approved' if fraud service is unavailable.
        \"\"\"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f\"{self.base_url}/check\",
                    json={\"payment_id\": payment_id, \"amount\": amount, \"user_id\": user_id},
                )
                response.raise_for_status()
                result = response.json()
                logger.info(\"fraud.check.completed\", payment_id=payment_id, risk=result.get(\"risk_level\"))
                return result
        except httpx.TimeoutException:
            logger.warning(\"fraud.check.timeout\", payment_id=payment_id, timeout=self.timeout)
            return {\"risk_level\": \"unknown\", \"approved\": True, \"reason\": \"fraud_service_timeout\"}
        except httpx.HTTPError as e:
            logger.error(\"fraud.check.error\", payment_id=payment_id, error=str(e))
            return {\"risk_level\": \"unknown\", \"approved\": True, \"reason\": \"fraud_service_unavailable\"}
"""),
    ])

    # ── COMMIT 11: Add payments router ────────────────────────────
    shas["c11"] = commit(REPO_ROOT, "Add payment endpoints", 15, [
        (REPO_ROOT / "app" / "routers" / "payments.py", """from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import time
from app.database import get_db
from app.repository import PaymentRepository
from app.schemas import PaymentCreate, PaymentResponse
from app.auth import get_current_user
from app.fraud_service import FraudServiceClient

router = APIRouter()
logger = structlog.get_logger(__name__)
fraud_client = FraudServiceClient()

@router.post(\"\", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    start = time.perf_counter()
    fraud_result = await fraud_client.check_payment(
        payment_id=\"pending\", amount=float(data.amount), user_id=data.user_id
    )
    if not fraud_result.get(\"approved\", True):
        raise HTTPException(status_code=422, detail=\"Payment rejected by fraud service\")
    repo = PaymentRepository(db)
    payment = await repo.create(data)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(\"payment.created\", payment_id=payment.id, latency_ms=latency_ms)
    return payment

@router.get(\"/{payment_id}\", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    repo = PaymentRepository(db)
    payment = await repo.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail=\"Payment not found\")
    return payment

@router.get(\"\", response_model=list[PaymentResponse])
async def list_payments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    repo = PaymentRepository(db)
    return await repo.get_all()
"""),
    ])

    # ── COMMIT 12: Add API tests ──────────────────────────────────
    shas["c12"] = commit(REPO_ROOT, "Add API integration tests", 17, [
        (REPO_ROOT / "tests" / "__init__.py", ""),
        (REPO_ROOT / "tests" / "test_payments.py", """import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=\"http://test\") as client:
        response = await client.get(\"/health\")
    assert response.status_code == 200
    assert response.json()[\"status\"] == \"healthy\"

@pytest.mark.asyncio
async def test_create_payment_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=\"http://test\") as client:
        response = await client.post(\"/payments\", json={
            \"user_id\": \"user-1\",
            \"amount\": \"100.00\",
        })
    assert response.status_code == 401
"""),
        (REPO_ROOT / "pytest.ini", """[pytest]
asyncio_mode = auto
"""),
    ])

    # ── COMMIT 13: Add error handling ─────────────────────────────
    shas["c13"] = commit(REPO_ROOT, "Improve error handling", 19, [
        (REPO_ROOT / "app" / "exceptions.py", """from fastapi import Request
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)

async def validation_exception_handler(request: Request, exc):
    logger.warning(\"request.validation_error\", path=request.url.path, errors=str(exc.errors()))
    return JSONResponse(status_code=422, content={\"detail\": exc.errors()})

async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(\"request.unhandled_error\", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={\"detail\": \"Internal server error\"})
"""),
    ])

    # ── COMMIT 14: Improve DB query performance ───────────────────
    shas["c14"] = commit(REPO_ROOT, "Improve database query performance", 21, [
        (REPO_ROOT / "app" / "repository.py", """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, Index
from app.models import Payment, PaymentStatus
from app.schemas import PaymentCreate
import structlog

logger = structlog.get_logger(__name__)

class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: PaymentCreate) -> Payment:
        payment = Payment(**data.model_dump())
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def get_by_id(self, payment_id: str) -> Payment | None:
        result = await self.db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[Payment]:
        # Added index hint via query ordering on indexed column
        result = await self.db.execute(
            select(Payment)
            .order_by(Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_user(self, user_id: str) -> list[Payment]:
        # Optimized: using indexed user_id column
        result = await self.db.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_payment_count(self) -> int:
        result = await self.db.execute(select(func.count(Payment.id)))
        return result.scalar_one()
"""),
    ])

    # ── COMMIT 15: Add payment history endpoint ───────────────────
    shas["c15"] = commit(REPO_ROOT, "Add payment history endpoint", 23, [
        (REPO_ROOT / "app" / "routers" / "payments.py", """from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import time
from app.database import get_db
from app.repository import PaymentRepository
from app.schemas import PaymentCreate, PaymentResponse
from app.auth import get_current_user
from app.fraud_service import FraudServiceClient

router = APIRouter()
logger = structlog.get_logger(__name__)
fraud_client = FraudServiceClient()

@router.post(\"\", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    start = time.perf_counter()
    fraud_result = await fraud_client.check_payment(
        payment_id=\"pending\", amount=float(data.amount), user_id=data.user_id
    )
    if not fraud_result.get(\"approved\", True):
        raise HTTPException(status_code=422, detail=\"Payment rejected by fraud service\")
    repo = PaymentRepository(db)
    payment = await repo.create(data)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(\"payment.created\", payment_id=payment.id, latency_ms=latency_ms)
    return payment

@router.get(\"/history\", response_model=list[PaymentResponse])
async def payment_history(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    \"\"\"Get payment history for a user.\"\"\"
    start = time.perf_counter()
    repo = PaymentRepository(db)
    payments = await repo.get_by_user(user_id)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(\"payment.history.retrieved\", user_id=user_id, count=len(payments), latency_ms=latency_ms)
    return payments

@router.get(\"/{payment_id}\", response_model=PaymentResponse)
async def get_payment(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    repo = PaymentRepository(db)
    payment = await repo.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail=\"Payment not found\")
    return payment

@router.get(\"\", response_model=list[PaymentResponse])
async def list_payments(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    repo = PaymentRepository(db)
    return await repo.get_all(limit=limit, offset=offset)
"""),
    ])

    # ── COMMIT 16: Service version bump ───────────────────────────
    shas["c16"] = commit(REPO_ROOT, "Release version 2.0.0", 25, [
        (REPO_ROOT / "app" / "config.py", """from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_version: str = \"2.0.0\"
    database_url: str = \"postgresql+asyncpg://payments:payments@localhost/payments\"
    jwt_secret: str = \"dev-secret\"
    jwt_algorithm: str = \"HS256\"
    jwt_expire_minutes: int = 30
    fraud_service_url: str = \"http://fraud-service:8001\"
    fraud_service_timeout: float = 5.0
    db_pool_size: int = 10
    db_max_overflow: int = 20

settings = Settings()
"""),
    ])

    # ── COMMIT 17: Add metrics endpoint ───────────────────────────
    shas["c17"] = commit(REPO_ROOT, "Add service metrics endpoint", 26, [
        (REPO_ROOT / "app" / "routers" / "health.py", """from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.repository import PaymentRepository

router = APIRouter()

@router.get(\"/health\")
async def health_check():
    return {
        \"status\": \"healthy\",
        \"service\": \"payment-api\",
        \"version\": settings.app_version,
    }

@router.get(\"/metrics\")
async def metrics(db: AsyncSession = Depends(get_db)):
    repo = PaymentRepository(db)
    total = await repo.get_payment_count()
    return {
        \"total_payments\": total,
        \"service\": \"payment-api\",
        \"version\": settings.app_version,
    }
"""),
    ])

    # ── COMMIT 18: Improve service logging ────────────────────────
    shas["c18"] = commit(REPO_ROOT, "Add service-level request logging middleware", 27, [
        (REPO_ROOT / "app" / "middleware.py", """import time
import uuid
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            \"request.completed\",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )
        structlog.contextvars.unbind_contextvars(\"request_id\")
        return response
"""),
    ])

    # ── COMMIT 19: Refactor to service layer ──────────────────────
    shas["c19"] = commit(REPO_ROOT, "Refactor payment logic into service layer", 28, [
        (REPO_ROOT / "app" / "services.py", """from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import structlog
from app.repository import PaymentRepository
from app.schemas import PaymentCreate
from app.models import Payment
from app.fraud_service import FraudServiceClient

logger = structlog.get_logger(__name__)

class PaymentService:
    def __init__(self, db: AsyncSession):
        self.repo = PaymentRepository(db)
        self.fraud_client = FraudServiceClient()

    async def create_payment(self, data: PaymentCreate) -> Payment:
        fraud_result = await self.fraud_client.check_payment(
            payment_id=\"pending\",
            amount=float(data.amount),
            user_id=data.user_id,
        )
        if not fraud_result.get(\"approved\", True):
            raise HTTPException(status_code=422, detail=\"Payment rejected by fraud service\")
        return await self.repo.create(data)
"""),
    ])

    # ── COMMIT 20: Version 2.1.0 ──────────────────────────────────
    shas["c20"] = commit(REPO_ROOT, "Release version 2.1.0", 29, [
        (REPO_ROOT / "app" / "config.py", """from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_version: str = \"2.1.0\"
    database_url: str = \"postgresql+asyncpg://payments:payments@localhost/payments\"
    jwt_secret: str = \"dev-secret\"
    jwt_algorithm: str = \"HS256\"
    jwt_expire_minutes: int = 30
    fraud_service_url: str = \"http://fraud-service:8001\"
    fraud_service_timeout: float = 5.0
    db_pool_size: int = 10
    db_max_overflow: int = 20

settings = Settings()
"""),
    ])

    # ── COMMIT 21: Add retry logic ────────────────────────────────
    shas["c21"] = commit(REPO_ROOT, "Add retry logic for external service calls", 30, [
        (REPO_ROOT / "app" / "fraud_service.py", """import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import settings

logger = structlog.get_logger(__name__)

class FraudServiceClient:
    def __init__(self):
        self.base_url = settings.fraud_service_url
        self.timeout = settings.fraud_service_timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def check_payment(self, payment_id: str, amount: float, user_id: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f\"{self.base_url}/check\",
                    json={\"payment_id\": payment_id, \"amount\": amount, \"user_id\": user_id},
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            logger.warning(\"fraud.check.timeout\", payment_id=payment_id)
            return {\"risk_level\": \"unknown\", \"approved\": True}
        except httpx.HTTPError as e:
            logger.error(\"fraud.check.error\", payment_id=payment_id, error=str(e))
            return {\"risk_level\": \"unknown\", \"approved\": True}
"""),
    ])

    # ── COMMIT 22: Add pagination ─────────────────────────────────
    shas["c22"] = commit(REPO_ROOT, "Add cursor-based pagination for payment history", 31, [
        (REPO_ROOT / "app" / "schemas.py", """from pydantic import BaseModel, field_validator
from decimal import Decimal
from datetime import datetime
from typing import Optional
from app.models import PaymentStatus

class PaymentCreate(BaseModel):
    user_id: str
    amount: Decimal
    currency: str = \"USD\"
    description: Optional[str] = None

    @field_validator(\"amount\")
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError(\"Amount must be positive\")
        return v

class PaymentResponse(BaseModel):
    id: str
    user_id: str
    amount: Decimal
    currency: str
    status: PaymentStatus
    description: Optional[str]
    created_at: datetime
    model_config = {\"from_attributes\": True}

class PaginatedPayments(BaseModel):
    items: list[PaymentResponse]
    total: int
    has_more: bool

class UserCreate(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = \"bearer\"
"""),
    ])

    # ── COMMIT 23: Version 2.2.0 ──────────────────────────────────
    shas["c23"] = commit(REPO_ROOT, "Release version 2.2.0", 32, [
        (REPO_ROOT / "app" / "config.py", """from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_version: str = \"2.2.0\"
    database_url: str = \"postgresql+asyncpg://payments:payments@localhost/payments\"
    jwt_secret: str = \"dev-secret\"
    jwt_algorithm: str = \"HS256\"
    jwt_expire_minutes: int = 30
    fraud_service_url: str = \"http://fraud-service:8001\"
    fraud_service_timeout: float = 5.0
    db_pool_size: int = 10
    db_max_overflow: int = 20

settings = Settings()
"""),
    ])

    print("\n" + "="*60)
    print("  DELIBERATE DEFECT COMMITS (INC-001 to INC-005)")
    print("="*60 + "\n")

    # ═══════════════════════════════════════════════════════════
    # INC-001: DB Connection Pool Exhaustion
    # Commit: "Improve database connection handling"
    # Defect: pool_size set to None → exhaustion under load
    # ═══════════════════════════════════════════════════════════
    shas["inc001"] = commit(REPO_ROOT, "Improve database connection handling", 35, [
        (REPO_ROOT / "app" / "config.py", """from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    app_version: str = \"2.3.0\"
    database_url: str = \"postgresql+asyncpg://payments:payments@localhost/payments\"
    jwt_secret: str = \"dev-secret\"
    jwt_algorithm: str = \"HS256\"
    jwt_expire_minutes: int = 30
    fraud_service_url: str = \"http://fraud-service:8001\"
    fraud_service_timeout: float = 5.0
    # BUG INC-001: pool_size set to None removes pool limit entirely
    # Under load, this exhausts all available DB connections
    db_pool_size: Optional[int] = None   # was: 10
    db_max_overflow: int = 0             # was: 20

settings = Settings()
"""),
        (REPO_ROOT / "app" / "database.py", """from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from collections.abc import AsyncGenerator
from app.config import settings

# BUG INC-001: When db_pool_size is None and db_max_overflow is 0,
# SQLAlchemy uses NullPool behavior — every request opens a new connection.
# Under load, this exhausts the PostgreSQL connection limit (100 by default).
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,     # None = use StaticPool (unbounded)
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_timeout=5,                       # very short — causes timeouts quickly
)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
"""),
    ])
    print(f"  ??  INC-001 commit SHA: {shas['inc001']} (DB pool exhaustion)")

    # ── COMMIT 24: Version 2.3.0 (with the bug) ──────────────────
    shas["c24"] = commit(REPO_ROOT, "Release version 2.3.0", 35.5, [
        (REPO_ROOT / "CHANGELOG.md", f"""# Changelog

## 2.3.0 (2026-09-{35:02d})
- Improved database connection handling for better performance
- Reduced connection overhead

## 2.2.0
- Added cursor-based pagination
- Performance improvements

## 2.1.0  
- Added retry logic for external services
- Service layer refactor

## 2.0.0
- Major refactor
- Payment history endpoint

## 1.0.0
- Initial release
"""),
    ])

    # ═══════════════════════════════════════════════════════════
    # INC-002: Slow SQL Query (N+1 problem)
    # Commit: "Optimize payment history retrieval"
    # Defect: removes indexed query, adds per-user subquery
    # ═══════════════════════════════════════════════════════════
    shas["inc002"] = commit(REPO_ROOT, "Optimize payment history retrieval", 36, [
        (REPO_ROOT / "app" / "repository.py", """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.models import Payment, User
from app.schemas import PaymentCreate
import structlog

logger = structlog.get_logger(__name__)

class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: PaymentCreate) -> Payment:
        payment = Payment(**data.model_dump())
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def get_by_id(self, payment_id: str) -> Payment | None:
        result = await self.db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[Payment]:
        result = await self.db.execute(
            select(Payment)
            .order_by(Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_user(self, user_id: str) -> list[Payment]:
        # BUG INC-002: This uses a correlated subquery instead of a simple WHERE clause.
        # For each payment row, PostgreSQL executes the subquery to get user data.
        # This is an N+1 query pattern — O(n) queries instead of O(1).
        # At scale (1000s of payments), latency goes from 30ms → 900ms.
        result = await self.db.execute(
            text(\"\"\"
                SELECT p.*
                FROM payments p
                WHERE p.user_id = (
                    SELECT id FROM users WHERE id = :user_id
                )
                ORDER BY p.created_at DESC
            \"\"\"),
            {\"user_id\": user_id}
        )
        rows = result.fetchall()
        # Manually construct Payment objects from raw rows (inefficient)
        payments = []
        for row in rows:
            p = Payment()
            for col, val in zip(result.keys(), row):
                setattr(p, col, val)
            payments.append(p)
        return payments

    async def get_payment_count(self) -> int:
        result = await self.db.execute(select(func.count(Payment.id)))
        return result.scalar_one()
"""),
    ])
    print(f"  ??  INC-002 commit SHA: {shas['inc002']} (Slow SQL N+1 query)")

    # ═══════════════════════════════════════════════════════════
    # INC-003: Memory Leak (unbounded cache)
    # Commit: "Add response caching"
    # Defect: cache grows without bound → OOM
    # ═══════════════════════════════════════════════════════════
    shas["inc003"] = commit(REPO_ROOT, "Add response caching", 37, [
        (REPO_ROOT / "app" / "cache.py", """\"\"\"
Response caching for payment-api.

BUG INC-003: This cache has NO eviction policy and NO size limit.
Every unique payment_id stored here stays forever.
Under normal traffic (thousands of payments/day), this will
exhaust available memory over 4-6 hours.
\"\"\"
import structlog

logger = structlog.get_logger(__name__)

# BUG: Module-level dictionary with no size limit or TTL
_cache: dict[str, dict] = {}

def get_cached_payment(payment_id: str) -> dict | None:
    result = _cache.get(payment_id)
    if result:
        logger.debug(\"cache.hit\", payment_id=payment_id, cache_size=len(_cache))
    return result

def cache_payment(payment_id: str, payment_data: dict) -> None:
    # BUG: No eviction — cache grows indefinitely
    _cache[payment_id] = payment_data
    logger.debug(\"cache.stored\", payment_id=payment_id, cache_size=len(_cache))

def invalidate_payment(payment_id: str) -> None:
    _cache.pop(payment_id, None)

def get_cache_stats() -> dict:
    return {\"size\": len(_cache), \"memory_estimate_mb\": len(_cache) * 0.002}
"""),
    ])
    print(f"  ??  INC-003 commit SHA: {shas['inc003']} (Memory leak, unbounded cache)")

    # ═══════════════════════════════════════════════════════════
    # INC-004: External Service Latency
    # Commit: "Improve external service integration"  
    # Defect: removes timeout from fraud service calls
    # ═══════════════════════════════════════════════════════════
    shas["inc004"] = commit(REPO_ROOT, "Improve external service integration", 38, [
        (REPO_ROOT / "app" / "fraud_service.py", """import httpx
import structlog
from app.config import settings

logger = structlog.get_logger(__name__)

class FraudServiceClient:
    \"\"\"
    BUG INC-004: Timeout removed from httpx client.
    When fraud-service latency increases (e.g. from 50ms to 8s),
    payment-api requests wait indefinitely. Thread pool exhausts.
    Payment API latency increases proportionally.
    \"\"\"
    def __init__(self):
        self.base_url = settings.fraud_service_url
        # BUG: timeout=None means wait forever
        # Previously: timeout=settings.fraud_service_timeout (5.0 seconds)

    async def check_payment(self, payment_id: str, amount: float, user_id: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=None) as client:  # BUG: no timeout
                response = await client.post(
                    f\"{self.base_url}/check\",
                    json={\"payment_id\": payment_id, \"amount\": amount, \"user_id\": user_id},
                )
                response.raise_for_status()
                result = response.json()
                logger.info(\"fraud.check.completed\", payment_id=payment_id)
                return result
        except httpx.HTTPError as e:
            logger.error(\"fraud.check.error\", error=str(e))
            return {\"risk_level\": \"unknown\", \"approved\": True}
"""),
    ])
    print(f"  ??  INC-004 commit SHA: {shas['inc004']} (External service timeout removed)")

    # ═══════════════════════════════════════════════════════════
    # INC-005: Authentication Regression
    # Commit: "Refactor JWT validation middleware"
    # Defect: algorithm changed from HS256 to 'none' check broken
    # ═══════════════════════════════════════════════════════════
    shas["inc005"] = commit(REPO_ROOT, "Refactor JWT validation middleware", 39, [
        (REPO_ROOT / "app" / "auth.py", """from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.config import settings
import structlog

pwd_context = CryptContext(schemes=[\"bcrypt\"], deprecated=\"auto\")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=\"/auth/login\")
logger = structlog.get_logger(__name__)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode[\"exp\"] = expire
    # BUG INC-005: Token created with HS256 (correct)
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=\"HS256\")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        # BUG INC-005: algorithms list now includes empty string and wrong value.
        # jose library raises JWTError when algorithm doesn't match,
        # but the real bug is: if settings.jwt_algorithm was accidentally
        # changed to \"RS256\" in env, validation fails for all existing HS256 tokens.
        # Simulated by using a mismatched algorithms list here:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[\"RS256\"],  # BUG: was [\"HS256\"] — all existing tokens now invalid
            options={\"verify_exp\": True}
        )
        user_id = payload.get(\"sub\")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=\"Invalid token\")
        logger.info(\"auth.validated\", user_id=user_id)
        return {\"user_id\": user_id}
    except JWTError as e:
        logger.warning(\"auth.validation_failed\", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=\"Could not validate credentials\",
            headers={\"WWW-Authenticate\": \"Bearer\"},
        )
"""),
    ])
    print(f"  ??  INC-005 commit SHA: {shas['inc005']} (JWT algorithm regression)")

    # ── COMMIT 25: Version 2.4.0 (defects included) ──────────────
    shas["c25"] = commit(REPO_ROOT, "Release version 2.4.0", 36.1, [
        (REPO_ROOT / "app" / "config.py", """from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    app_version: str = \"2.4.0\"
    database_url: str = \"postgresql+asyncpg://payments:payments@localhost/payments\"
    jwt_secret: str = \"dev-secret\"
    jwt_algorithm: str = \"HS256\"
    jwt_expire_minutes: int = 30
    fraud_service_url: str = \"http://fraud-service:8001\"
    fraud_service_timeout: float = 5.0
    db_pool_size: Optional[int] = None
    db_max_overflow: int = 0

settings = Settings()
"""),
    ])

    # ── COMMIT 26-30: Normal maintenance commits ──────────────────
    for idx, (msg, day) in enumerate([
        ("Update dependencies", 40),
        ("Fix typo in payment response schema", 41),
        ("Add request ID to log context", 42),
        ("Update README with deployment instructions", 43),
        ("Add Docker support for payment-api", 44),
    ], start=26):
        shas[f"c{idx}"] = commit(REPO_ROOT, msg, day, [
            (REPO_ROOT / "docs" / f"note_{idx}.md", f"# {msg}\n\nUpdated {day} days after initial commit.\n"),
        ])

    print("\n" + "="*60)
    print("  GIT HISTORY COMPLETE")
    print("="*60)
    print(f"\nTotal commits: ~{len(shas)}")
    print("\nDefect commit SHAs (for ground truth):")
    for key in ["inc001", "inc002", "inc003", "inc004", "inc005"]:
        print(f"  {key.upper()}: {shas[key]}")

    # Write SHA mapping for seed_data.py to use
    import json
    sha_file = REPO_ROOT.parent.parent / "test-data" / "commit_shas.json"
    sha_file.parent.mkdir(parents=True, exist_ok=True)
    sha_file.write_text(json.dumps(shas, indent=2))
    print(f"\nSHAs written to: {sha_file}")


if __name__ == "__main__":
    build_history()
