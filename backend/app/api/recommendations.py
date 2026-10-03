"""Recommendations approval/rejection endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import get_db
from app.security.dependencies import get_current_user, require_sre
from app.models import Recommendation, RecommendationStatus, Approval, User

router = APIRouter()


class ApprovalRequest(BaseModel):
    reason: str = ""


@router.post("/{recommendation_id}/approve")
async def approve_recommendation(
    recommendation_id: str,
    data: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_sre),
):
    """
    Human approval for a HIGH/MEDIUM risk recommendation.
    Records the decision — does NOT execute any real action.
    """
    result = await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = RecommendationStatus.APPROVED
    approval = Approval(
        id=str(uuid.uuid4()),
        recommendation_id=recommendation_id,
        user_id=current_user.id,
        decision="APPROVED",
        reason=data.reason,
    )
    db.add(approval)
    await db.commit()

    return {
        "status": "APPROVED",
        "recommendation_id": recommendation_id,
        "approved_by": current_user.email,
        "note": "SIMULATED — No real action was taken. This is an MVP demo environment.",
    }


@router.post("/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: str,
    data: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_sre),
):
    result = await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = RecommendationStatus.REJECTED
    approval = Approval(
        id=str(uuid.uuid4()),
        recommendation_id=recommendation_id,
        user_id=current_user.id,
        decision="REJECTED",
        reason=data.reason,
    )
    db.add(approval)
    await db.commit()

    return {
        "status": "REJECTED",
        "recommendation_id": recommendation_id,
        "rejected_by": current_user.email,
    }
