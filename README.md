# RootTrace

> **Agentic AI for Evidence-Driven Incident Investigation**

RootTrace is an AI-powered software incident investigation platform that investigates software incidents the way a senior SRE would — by collecting real evidence, generating competing hypotheses, testing each against that evidence, and recommending safe remediation.

## Architecture

```
Frontend (Next.js) → Backend (FastAPI) → LangGraph Agent
                                              ↓
                               7 Investigation Tools
                                              ↓
                         PostgreSQL + pgvector (RAG + all data)
                                              ↓
                            Incident Lab (payment-api + test data)
```

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Python 3.12 (for local development)
- Node.js 20+ (for frontend development)
- A Google Gemini API key

### 1. Clone and configure
```bash
git clone <repo>
cd roottrace
cp .env.example .env
# Edit .env — fill in GEMINI_API_KEY and JWT_SECRET
```

### 2. Start infrastructure
```bash
docker compose up postgres -d
# Wait for postgres to be healthy
```

### 3. Set up the backend
```bash
cd backend
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Build the incident lab Git history (creates payment-api with 35+ commits)
python scripts/build_git_history.py

# Seed test data (deployments, logs, metrics)
python scripts/seed_data.py

# Ingest knowledge base documents into pgvector
python scripts/ingest_knowledge_base.py
```

### 4. Start the backend
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Start the frontend
```bash
cd frontend
npm install
npm run dev
```

### 6. Open RootTrace
Navigate to http://localhost:3000

Login with:
- `sre@roottrace.dev` / `sre123` (SRE role — can approve recommendations)
- `dev@roottrace.dev` / `dev123` (developer role)
- `admin@roottrace.dev` / `admin123` (admin role)

## Demo Scenario

1. Create incident: "Payment API latency increased 300% after latest deployment"
2. Service: `payment-api`, Time: `2026-09-06T10:30:00Z`
3. Click "Start Investigation"
4. Watch the live timeline as the agent:
   - Finds DEP-001 (deployed at 10:20)
   - Finds commit with `db_pool_size=None`
   - Finds DB connections at 100/100
   - Finds connection timeout log errors
   - Retrieves RUNBOOK-001 and postmortem INC-042
5. Agent generates 3 hypotheses with scores
6. Validates H1 (DB pool exhaustion) as SUPPORTED at ~86/100
7. Recommends rollback — requires human approval
8. Click Approve → decision recorded (no real action taken)

## Running Evaluations

```bash
cd backend
python scripts/run_evaluation.py
```

Results are saved to `incident-lab/evaluation/results.json` and `report.md`.

## Environment Variables

See [.env.example](.env.example) for all required configuration.

## Project Structure

```
roottrace/
├── backend/           # FastAPI + LangGraph agent
│   ├── app/
│   │   ├── api/       # REST endpoints
│   │   ├── agents/    # LangGraph nodes
│   │   ├── workflows/ # Investigation graph
│   │   ├── tools/     # 7 investigation tools
│   │   ├── retrieval/ # RAG pipeline
│   │   └── core/      # Config, DB, LLM
│   └── scripts/       # Setup, seed, evaluation
├── frontend/          # Next.js UI
└── incident-lab/      # Test environment
    ├── payment-api/   # FastAPI test service (35+ commits)
    ├── knowledge-base/# Runbooks, postmortems, architecture docs
    └── evaluation/    # Ground truth + results
```

## Security Notes

- JWT secrets and API keys must be set in `.env` — never committed
- High/medium risk actions require human approval — never executed autonomously
- Retrieved documents are treated as untrusted data (prompt injection defense)
- Git operations use subprocess argument arrays — no shell injection
