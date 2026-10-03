"""Evaluation endpoint — returns benchmark results."""
from fastapi import APIRouter, Depends
from app.security.dependencies import get_current_user
from app.models import User
import json
from pathlib import Path

router = APIRouter()

RESULTS_FILE = Path(__file__).parent.parent.parent.parent / "incident-lab" / "evaluation" / "results.json"


@router.get("/results")
async def get_evaluation_results(current_user: User = Depends(get_current_user)):
    """Return the latest benchmark evaluation results."""
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return {
        "status": "no_results",
        "message": "Run scripts/run_evaluation.py to generate results",
    }
