"""
Investigation Service
======================
Business logic for managing the investigation lifecycle.

Separates the "trigger investigation" logic from the FastAPI route handler,
making it testable and reusable.

The actual investigation graph runs in a background task. This service
manages state transitions and database bookkeeping around that.
"""

import uuid
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Incident,
    IncidentStatus,
    InvestigationEvent,
    InvestigationEventType,
    Recommendation,
    RecommendationStatus,
    Approval,
)
from app.services.incident_service import IncidentService

logger = structlog.get_logger(__name__)


class InvestigationService:
    """
    Service layer for investigation lifecycle management.

    Handles:
    - Status transitions (OPEN → INVESTIGATING → RESOLVED)
    - Event logging
    - Approval workflow
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.incidents = IncidentService(db)

    # ── Investigation Trigger ─────────────────────────────────

    async def can_start_investigation(self, incident_id: str) -> tuple[bool, str]:
        """
        Check whether an investigation can be started.

        Returns (ok, error_message). If ok is True, error_message is empty.
        """
        incident = await self.incidents.get_incident(incident_id)
        if not incident:
            return False, "Incident not found"
        if incident.status == IncidentStatus.INVESTIGATING:
            return False, "Investigation already in progress"
        return True, ""

    async def mark_investigating(self, incident_id: str) -> None:
        """
        Transition incident to INVESTIGATING and write the opening event.
        Call this before launching the background investigation task.
        """
        incident = await self.incidents.get_incident(incident_id)
        if incident:
            incident.status = IncidentStatus.INVESTIGATING

        event = InvestigationEvent(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            agent_node="system",
            event_type=InvestigationEventType.INCIDENT_RECEIVED,
            summary=f"Investigation triggered for incident: {incident.title if incident else incident_id}",
        )
        self.db.add(event)
        await self.db.commit()
        logger.info("investigation_service.started", incident_id=incident_id)

    # ── Approval Workflow ─────────────────────────────────────

    async def get_recommendation(self, recommendation_id: str) -> Recommendation | None:
        """Fetch a recommendation by ID."""
        result = await self.db.execute(
            select(Recommendation).where(Recommendation.id == recommendation_id)
        )
        return result.scalar_one_or_none()

    async def approve_recommendation(
        self,
        recommendation_id: str,
        user_id: str,
        reason: str = "",
    ) -> Approval:
        """Record a human approval decision for a recommendation."""
        rec = await self.get_recommendation(recommendation_id)
        if not rec:
            raise ValueError(f"Recommendation {recommendation_id!r} not found")

        rec.status = RecommendationStatus.APPROVED
        approval = Approval(
            id=str(uuid.uuid4()),
            recommendation_id=recommendation_id,
            user_id=user_id,
            decision="APPROVED",
            reason=reason,
        )
        self.db.add(approval)
        await self.db.commit()

        logger.info(
            "investigation_service.recommendation_approved",
            recommendation_id=recommendation_id,
            user_id=user_id,
        )
        return approval

    async def reject_recommendation(
        self,
        recommendation_id: str,
        user_id: str,
        reason: str = "",
    ) -> Approval:
        """Record a human rejection decision for a recommendation."""
        rec = await self.get_recommendation(recommendation_id)
        if not rec:
            raise ValueError(f"Recommendation {recommendation_id!r} not found")

        rec.status = RecommendationStatus.REJECTED
        approval = Approval(
            id=str(uuid.uuid4()),
            recommendation_id=recommendation_id,
            user_id=user_id,
            decision="REJECTED",
            reason=reason,
        )
        self.db.add(approval)
        await self.db.commit()

        logger.info(
            "investigation_service.recommendation_rejected",
            recommendation_id=recommendation_id,
            user_id=user_id,
        )
        return approval

    # ── Event Logging ─────────────────────────────────────────

    async def log_event(
        self,
        incident_id: str,
        event_type: InvestigationEventType,
        *,
        agent_node: str | None = None,
        tool_name: str | None = None,
        summary: str | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> InvestigationEvent:
        """Write a single investigation event to the audit log."""
        event = InvestigationEvent(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            agent_node=agent_node,
            event_type=event_type,
            tool_name=tool_name,
            summary=summary,
            success=success,
            error_message=error_message,
        )
        self.db.add(event)
        await self.db.commit()
        return event
