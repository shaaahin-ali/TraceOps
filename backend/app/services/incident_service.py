"""
Incident Service
=================
Business logic for incident CRUD operations.

Centralises DB queries that were previously scattered across API routes.
This makes the logic testable without spinning up the HTTP layer.

Usage:
    from app.services.incident_service import IncidentService
    service = IncidentService(db)
    incidents = await service.list_incidents()
"""

import uuid
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Hypothesis,
    Evidence,
    Recommendation,
    InvestigationEvent,
)

logger = structlog.get_logger(__name__)


class IncidentService:
    """
    Service layer for Incident-related DB operations.

    Why a class rather than free functions?
    - Binds the AsyncSession once, so callers don't repeat Depends(get_db)
    - Easy to mock in tests: pass a mock session to __init__
    - Keeps route handlers thin — they call service methods, not raw SQL
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Read ──────────────────────────────────────────────────

    async def list_incidents(self, limit: int = 50) -> list[Incident]:
        """Return the most recently created incidents."""
        result = await self.db.execute(
            select(Incident).order_by(Incident.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Return a single incident by ID, or None if not found."""
        result = await self.db.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def get_events(self, incident_id: str) -> list[InvestigationEvent]:
        """Return all investigation events for an incident, ordered by time."""
        result = await self.db.execute(
            select(InvestigationEvent)
            .where(InvestigationEvent.incident_id == incident_id)
            .order_by(InvestigationEvent.timestamp.asc())
        )
        return list(result.scalars().all())

    async def get_hypotheses(self, incident_id: str) -> list[Hypothesis]:
        """Return hypotheses for an incident, ordered by rank."""
        result = await self.db.execute(
            select(Hypothesis)
            .where(Hypothesis.incident_id == incident_id)
            .order_by(Hypothesis.rank.asc())
        )
        return list(result.scalars().all())

    async def get_evidence(self, incident_id: str) -> list[Evidence]:
        """Return collected evidence for an incident, ordered by relevance."""
        result = await self.db.execute(
            select(Evidence)
            .where(Evidence.incident_id == incident_id)
            .order_by(Evidence.relevance_score.desc())
        )
        return list(result.scalars().all())

    async def get_recommendations(self, incident_id: str) -> list[Recommendation]:
        """Return remediation recommendations for an incident."""
        result = await self.db.execute(
            select(Recommendation)
            .where(Recommendation.incident_id == incident_id)
        )
        return list(result.scalars().all())

    # ── Write ─────────────────────────────────────────────────

    async def create_incident(
        self,
        *,
        title: str,
        description: str,
        service: str,
        severity: str = "MEDIUM",
        incident_time: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Incident:
        """
        Create and persist a new incident.

        Converts raw strings into the correct ORM types.
        Returns the refreshed ORM object so callers have all DB-generated fields.
        """
        incident = Incident(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            service=service,
            severity=IncidentSeverity(severity.upper()),
            status=IncidentStatus.OPEN,
            incident_time=(
                datetime.fromisoformat(incident_time.replace("Z", "+00:00"))
                if incident_time
                else None
            ),
            created_by=created_by,
        )
        self.db.add(incident)
        await self.db.commit()
        await self.db.refresh(incident)
        logger.info("incident_service.created", incident_id=incident.id, service=service)
        return incident

    async def update_status(self, incident_id: str, status: IncidentStatus) -> Optional[Incident]:
        """Update an incident's status field."""
        incident = await self.get_incident(incident_id)
        if not incident:
            return None
        incident.status = status
        await self.db.commit()
        return incident
