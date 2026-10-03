"""Documents API — ingestion and listing."""
from fastapi import APIRouter, Depends, BackgroundTasks
from app.core.database import get_db
from app.security.dependencies import get_current_user
from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.post("/ingest")
async def trigger_ingestion(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger knowledge base re-ingestion in the background."""
    async def run_ingestion():
        import subprocess, sys
        subprocess.run([sys.executable, "scripts/ingest_knowledge_base.py"], capture_output=True)

    background_tasks.add_task(run_ingestion)
    return {"status": "ingestion_started", "message": "Knowledge base ingestion running in background"}
