# RootTrace Setup Guide — Docker Desktop + First Run

## Step 1: Install Docker Desktop

1. Download from: https://www.docker.com/products/docker-desktop/
2. Run the installer
3. **Restart your computer** after installation
4. Open Docker Desktop and wait for it to show "Docker is running" (green dot)
5. Open a new terminal and verify: `docker --version`

---

## Step 2: Set Your Gemini API Key

```powershell
cd C:\Users\shahi\TraceOps\roottrace
Copy-Item .env.example .env
```

Edit `.env` and set:
```
GEMINI_API_KEY=your-key-here          # From aistudio.google.com
JWT_SECRET=your-random-32-char-secret # e.g., openssl rand -hex 32
```

You can get a free Gemini API key at: https://aistudio.google.com/app/apikey

---

## Step 3: Start PostgreSQL

```powershell
cd C:\Users\shahi\TraceOps\roottrace
docker compose up postgres -d
```

Wait ~15 seconds for PostgreSQL to initialize, then verify:
```powershell
docker compose ps
```
Should show `postgres` as `healthy`.

---

## Step 4: Initialize the Database

```powershell
cd C:\Users\shahi\TraceOps\roottrace\backend

# Run migrations (creates all 12 tables)
python -m alembic upgrade head

# Seed test data (logs, metrics, deployments for all 5 incidents)
python scripts/seed_data.py
```

Expected output from seed_data.py:
```
[OK] 3 users created
[OK] 5 deployment records created
[OK] 46 log entries created
[OK] 41 metric data points created
Seed data complete!
```

---

## Step 5: Ingest Knowledge Base (RAG)

```powershell
python scripts/ingest_knowledge_base.py
```

This step embeds all runbooks, postmortems, and architecture docs into pgvector.
It requires your `GEMINI_API_KEY` to be set. Takes ~30-60 seconds.

Expected output:
```
[OK] database-connections.md -> 4 chunks embedded
[OK] memory-leak.md -> 3 chunks embedded
...
HNSW index created for fast vector search
```

---

## Step 6: Start the Backend API

```powershell
cd C:\Users\shahi\TraceOps\roottrace\backend
uvicorn app.main:app --reload --port 8000
```

Verify it's running: open http://localhost:8000/api/health

---

## Step 7: Start the Frontend

In a new terminal:
```powershell
cd C:\Users\shahi\TraceOps\roottrace\frontend
npm run dev
```

Open http://localhost:3000 → should redirect to login.

---

## Step 8: Run Your First Investigation

1. Login with `sre@roottrace.dev` / `sre123`
2. Click **New Investigation**
3. Fill in:
   - **Title**: `Payment API latency increased 300% after latest deployment`
   - **Description**: `Users experiencing payment processing delays. Issue started ~10 minutes after latest deployment. API response times went from 120ms to 600ms+. Some requests timing out.`
   - **Service**: `payment-api`
   - **Severity**: `HIGH`
   - **Incident Time**: `2026-09-06T10:30:00`
4. Click **Start Investigation**
5. Watch the Timeline tab update in real time as the agent investigates

The investigation takes ~2-5 minutes. You'll see:
- Deployment DEP-001 found at 10:20
- Commit `3276a32` identified with `db_pool_size=None`
- DB connections metric at 100/100 confirmed
- QueuePool timeout errors in logs
- Historical postmortem INC-042 retrieved (similar incident)
- 3+ hypotheses generated, H1 (DB pool exhaustion) validated as SUPPORTED
- Rollback recommendation created
- Approval gate triggered → click Approve to record decision

---

## Troubleshooting

### "connection refused" errors
→ PostgreSQL isn't running yet. Run `docker compose up postgres -d`

### "GEMINI_API_KEY not set" error
→ Make sure `.env` exists and has the key set

### Alembic migration fails with "pgvector not found"
→ The `init_db.sql` is already handled by our docker-compose postgres image.
   If using a custom Postgres, run: `CREATE EXTENSION IF NOT EXISTS vector;`

### Frontend shows blank page
→ Make sure the backend is running on port 8000 before starting the frontend

---

## Quick Command Reference

```powershell
# Start everything
docker compose up postgres -d
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev

# Run evaluation benchmark
cd backend
python scripts/run_evaluation.py

# Reset and re-seed data
python scripts/seed_data.py
```
