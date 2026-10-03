"""
RootTrace Seed Data Script
============================
Populates the database with:
1. Test users
2. 5 incident scenarios (INC-001 to INC-005)
3. Realistic simulated logs (with anomalies baked in)
4. Simulated deployment records
5. Simulated metric time-series (with spikes)
6. Historical incidents for RAG search

🎓 WHY SEED DATA?
The AI agent calls search_logs(), search_metrics(), search_deployments()
during investigation. These tools query the database.
Without seed data, the tools return empty results and investigation fails.
Seed data creates the controlled environment the agent investigates.

Run: python scripts/seed_data.py
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

# Load incident commit SHAs if available
SHA_FILE = Path(__file__).parent.parent.parent / "incident-lab" / "test-data" / "commit_shas.json"
commit_shas = {}
if SHA_FILE.exists():
    commit_shas = json.loads(SHA_FILE.read_text())

from app.core.config import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url

# ── Timeline Reference ────────────────────────────────────────
# All incidents happen relative to this base time
# INC-001: Sep 6, 2026 — DB pool exhaustion
# INC-002: Sep 7, 2026 — Slow SQL
# INC-003: Sep 8, 2026 — Memory leak
# INC-004: Sep 9, 2026 — External service
# INC-005: Sep 10, 2026 — Auth regression

def dt(day: int, hour: int, minute: int = 0, second: int = 0) -> str:
    """Create a UTC ISO timestamp for September 2026."""
    d = datetime(2026, 9, day, hour, minute, second, tzinfo=timezone.utc)
    return d.isoformat()


async def seed(db: AsyncSession):
    print("🌱 Seeding RootTrace database...\n")

    # ── Users ─────────────────────────────────────────────────
    print("  👤 Creating users...")
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

    users = [
        {"id": "user-admin-001", "name": "Admin User", "email": "admin@roottrace.dev",
         "password_hash": pwd.hash("admin123"), "role": "ADMIN"},
        {"id": "user-sre-001", "name": "Sarah Chen", "email": "sre@roottrace.dev",
         "password_hash": pwd.hash("sre123"), "role": "SRE"},
        {"id": "user-dev-001", "name": "Alex Kumar", "email": "dev@roottrace.dev",
         "password_hash": pwd.hash("dev123"), "role": "USER"},
    ]
    for u in users:
        await db.execute(text("""
            INSERT INTO users (id, name, email, password_hash, role, is_active, created_at)
            VALUES (:id, :name, :email, :password_hash, :role, true, NOW())
            ON CONFLICT (email) DO NOTHING
        """), u)
    print(f"  ✓ {len(users)} users created")

    # ── Deployments ───────────────────────────────────────────
    print("\n  🚀 Creating deployment records...")
    deployments = [
        {
            "id": "DEP-001", "service": "payment-api", "version": "2.3.0",
            "commit_sha": commit_shas.get("inc001", "a72f19abc123"),
            "status": "SUCCESS", "deployed_at": dt(6, 10, 20),
            "deployed_by": "github-actions",
            "deployment_metadata": json.dumps({"trigger": "merge", "branch": "main", "pr": "PR-441"})
        },
        {
            "id": "DEP-002", "service": "payment-api", "version": "2.3.1",
            "commit_sha": commit_shas.get("inc002", "b812ac789def"),
            "status": "SUCCESS", "deployed_at": dt(7, 14, 15),
            "deployed_by": "github-actions",
            "deployment_metadata": json.dumps({"trigger": "merge", "branch": "main", "pr": "PR-447"})
        },
        {
            "id": "DEP-003", "service": "payment-api", "version": "2.3.2",
            "commit_sha": commit_shas.get("inc003", "c812fe456ghi"),
            "status": "SUCCESS", "deployed_at": dt(8, 9, 0),
            "deployed_by": "github-actions",
            "deployment_metadata": json.dumps({"trigger": "merge", "branch": "main", "pr": "PR-452"})
        },
        {
            "id": "DEP-004", "service": "payment-api", "version": "2.3.3",
            "commit_sha": commit_shas.get("inc004", "d921fg123jkl"),
            "status": "SUCCESS", "deployed_at": dt(9, 11, 30),
            "deployed_by": "github-actions",
            "deployment_metadata": json.dumps({"trigger": "merge", "branch": "main", "pr": "PR-458"})
        },
        {
            "id": "DEP-005", "service": "payment-api", "version": "2.4.0",
            "commit_sha": commit_shas.get("inc005", "e044hi789mno"),
            "status": "SUCCESS", "deployed_at": dt(10, 16, 45),
            "deployed_by": "github-actions",
            "deployment_metadata": json.dumps({"trigger": "merge", "branch": "main", "pr": "PR-461"})
        },
    ]
    for d in deployments:
        await db.execute(text("""
            INSERT INTO deployments (id, service, version, commit_sha, status, deployed_at, deployed_by, deployment_metadata)
            VALUES (:id, :service, :version, :commit_sha, :status, :deployed_at, :deployed_by, :deployment_metadata::jsonb)
            ON CONFLICT (id) DO NOTHING
        """), d)
    print(f"  ✓ {len(deployments)} deployment records created")

    # ── Logs — INC-001: DB Pool Exhaustion ───────────────────
    print("\n  📋 Creating log entries...")
    logs = []

    # Normal logs before DEP-001
    for i in range(20):
        minute = i * 3
        logs.append({
            "id": str(uuid.uuid4()), "service": "payment-api",
            "timestamp": dt(6, 9, minute % 60, 0),
            "level": "INFO", "message": f"request completed",
            "request_id": f"req-{uuid.uuid4().hex[:8]}",
            "log_metadata": json.dumps({"latency_ms": 115 + (i % 15), "path": "/payments", "method": "POST"})
        })

    # DEP-001 deployed at 10:20 — logs after show degradation
    logs.append({
        "id": str(uuid.uuid4()), "service": "payment-api",
        "timestamp": dt(6, 10, 20, 5),
        "level": "INFO", "message": "deployment complete: version=2.3.0 commit=a72f19",
        "request_id": "deploy-dep001",
        "log_metadata": json.dumps({"deployment_id": "DEP-001", "version": "2.3.0"})
    })

    # Connection pool pressure starts building
    logs.extend([
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(6, 10, 25),
         "level": "WARN", "message": "database connection acquisition slow",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"latency_ms": 410, "pool_size": 85, "pool_timeout_remaining_ms": 590})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(6, 10, 26),
         "level": "WARN", "message": "database connection acquisition slow",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"latency_ms": 850, "pool_size": 95, "pool_timeout_remaining_ms": 150})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(6, 10, 26, 30),
         "level": "ERROR", "message": "database connection timeout: pool exhausted after 5000ms",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"pool_size": 100, "max_overflow": 0, "error": "QueuePool limit reached"})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(6, 10, 27),
         "level": "ERROR", "message": "database connection timeout: pool exhausted after 5000ms",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"pool_size": 100, "error": "QueuePool limit reached"})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(6, 10, 27, 15),
         "level": "WARN", "message": "payment request latency elevated",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"latency_ms": 1250, "threshold_ms": 500})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(6, 10, 28),
         "level": "ERROR", "message": "payment request failed: database unavailable",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"error": "QueuePool limit reached", "user_id": "user-99"})},
    ])

    # INC-002: Slow SQL — payment history endpoint
    logs.extend([
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(7, 14, 30),
         "level": "INFO", "message": "payment.history.retrieved",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"user_id": "user-55", "count": 45, "latency_ms": 28})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(7, 14, 45),
         "level": "WARN", "message": "payment.history.retrieved — latency threshold exceeded",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"user_id": "user-55", "count": 47, "latency_ms": 920})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(7, 15, 0),
         "level": "ERROR", "message": "database query timeout on payment history retrieval",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"query": "SELECT p.* FROM payments p WHERE p.user_id = (SELECT id FROM users WHERE id = $1)", "latency_ms": 3200, "timeout_ms": 3000})},
    ])

    # INC-003: Memory leak
    logs.extend([
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(8, 12, 0),
         "level": "INFO", "message": "cache.stored", "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"payment_id": "pay-001", "cache_size": 1200})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(8, 14, 0),
         "level": "WARN", "message": "high memory usage detected",
         "request_id": "system-monitor",
         "log_metadata": json.dumps({"memory_percent": 78, "cache_size": 8500})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(8, 15, 30),
         "level": "ERROR", "message": "OOM killer triggered — process restarted",
         "request_id": "system-monitor",
         "log_metadata": json.dumps({"memory_percent": 98, "cache_size": 15200, "oom_score": 900})},
    ])

    # INC-004: Fraud service latency
    logs.extend([
        {"id": str(uuid.uuid4()), "service": "fraud-service", "timestamp": dt(9, 13, 0),
         "level": "WARN", "message": "fraud check processing slow",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"latency_ms": 2100})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(9, 13, 5),
         "level": "WARN", "message": "fraud.check waiting — no timeout configured",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"wait_ms": 2100, "payment_id": "pay-002"})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(9, 13, 10),
         "level": "ERROR", "message": "payment request latency elevated — fraud service dependency",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"latency_ms": 8200, "fraud_service_latency_ms": 8100})},
    ])

    # INC-005: Auth failures
    logs.extend([
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(10, 17, 0),
         "level": "WARN", "message": "auth.validation_failed",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"error": "Signature verification failed", "algorithm": "RS256"})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(10, 17, 1),
         "level": "WARN", "message": "auth.validation_failed",
         "request_id": f"req-{uuid.uuid4().hex[:8]}",
         "log_metadata": json.dumps({"error": "Signature verification failed", "algorithm": "RS256"})},
        {"id": str(uuid.uuid4()), "service": "payment-api", "timestamp": dt(10, 17, 2),
         "level": "ERROR", "message": "401 error rate spike detected — 100% of authenticated requests failing",
         "request_id": "alert-system",
         "log_metadata": json.dumps({"error_rate": 1.0, "http_status": 401, "time_window_seconds": 60})},
    ])

    for log in logs:
        await db.execute(text("""
            INSERT INTO logs (id, service, timestamp, level, message, request_id, log_metadata)
            VALUES (:id, :service, :timestamp, :level, :message, :request_id, :log_metadata::jsonb)
            ON CONFLICT (id) DO NOTHING
        """), log)
    print(f"  ✓ {len(logs)} log entries created")

    # ── Metrics ───────────────────────────────────────────────
    print("\n  📊 Creating metric time series...")
    metrics = []

    def add_metric(service, metric, day, hour, minute, value):
        metrics.append({
            "id": str(uuid.uuid4()), "service": service,
            "metric_name": metric, "timestamp": dt(day, hour, minute),
            "value": float(value), "metric_metadata": json.dumps({})
        })

    # INC-001 metrics: DB connections exploding after DEP-001 at 10:20
    for m, val in [(10, 0), (15, 30), (20, 35), (21, 45), (22, 65), (23, 85), (24, 95), (25, 100), (26, 100), (27, 100)]:
        add_metric("payment-api", "db_connections", 6, 10, m, val)
    for m, val in [(10, 120), (15, 125), (20, 130), (21, 220), (22, 380), (23, 550), (24, 620), (25, 680), (26, 700), (27, 750)]:
        add_metric("payment-api", "api_latency_ms", 6, 10, m, val)
    for m, val in [(10, 0.01), (20, 0.01), (25, 0.12), (26, 0.45), (27, 0.72)]:
        add_metric("payment-api", "error_rate", 6, 10, m, val)

    # INC-002 metrics: query latency spikes
    for m, val in [(0, 28), (30, 35), (45, 920), (50, 1100), (55, 1350)]:
        add_metric("payment-api", "db_query_latency_ms", 7, 14, m, val)
    for m, val in [(0, 145), (30, 155), (45, 1050), (50, 1200), (55, 1450)]:
        add_metric("payment-api", "api_latency_ms", 7, 14, m, val)

    # INC-003 metrics: memory creeping up
    for h, val in [(9, 42), (10, 48), (11, 55), (12, 63), (13, 71), (14, 79), (15, 92), (15, 98)]:
        add_metric("payment-api", "memory_percent", 8, h, 0 if h != 15 else 30, val)

    # INC-004 metrics: fraud service latency → API latency
    for m, val in [(0, 55), (30, 65), (45, 2100), (50, 4500), (55, 8200)]:
        add_metric("fraud-service", "response_latency_ms", 9, 13, m, val)
    for m, val in [(0, 140), (30, 150), (45, 2200), (50, 4600), (55, 8300)]:
        add_metric("payment-api", "api_latency_ms", 9, 13, m, val)

    # INC-005 metrics: 401 rate
    for m, val in [(0, 0.0), (45, 0.0), (50, 0.15), (55, 0.65), (58, 0.95), (59, 1.0)]:
        add_metric("payment-api", "error_rate", 10, 16, m, val)

    for m in metrics:
        await db.execute(text("""
            INSERT INTO metrics (id, service, metric_name, timestamp, value, metric_metadata)
            VALUES (:id, :service, :metric_name, :timestamp, :value, :metric_metadata::jsonb)
            ON CONFLICT (id) DO NOTHING
        """), m)
    print(f"  ✓ {len(metrics)} metric data points created")

    await db.commit()
    print("\n✅ Seed data complete!\n")
    print("Test accounts:")
    print("  admin@roottrace.dev  / admin123  (ADMIN)")
    print("  sre@roottrace.dev    / sre123    (SRE)")
    print("  dev@roottrace.dev    / dev123    (USER)")


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
