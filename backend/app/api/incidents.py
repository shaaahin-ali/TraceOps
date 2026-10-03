"""
Incidents + Investigations API
================================
Incident CRUD and investigation trigger endpoints.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import (
    Incident, IncidentSeverity, IncidentStatus,
    Hypothesis, Evidence, Recommendation, InvestigationEvent, InvestigationEventType,
)
from app.security.dependencies import get_current_user
from app.models import User

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────

class IncidentCreate(BaseModel):
    title: str
    description: str
    service: str
    severity: str = "MEDIUM"
    incident_time: Optional[str] = None


class IncidentResponse(BaseModel):
    id: str
    title: str
    description: str
    service: str
    severity: str
    status: str
    incident_time: Optional[str]
    created_at: str
    confidence_score: Optional[float]
    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────

@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Incident).order_by(Incident.created_at.desc()).limit(50)
    )
    incidents = result.scalars().all()
    return [
        IncidentResponse(
            id=i.id, title=i.title, description=i.description,
            service=i.service, severity=i.severity.value if hasattr(i.severity, "value") else i.severity,
            status=i.status.value if hasattr(i.status, "value") else i.status,
            incident_time=i.incident_time.isoformat() if i.incident_time else None,
            created_at=i.created_at.isoformat(),
            confidence_score=i.confidence_score,
        )
        for i in incidents
    ]


@router.post("", response_model=IncidentResponse, status_code=201)
async def create_incident(
    data: IncidentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = Incident(
        id=str(uuid.uuid4()),
        title=data.title,
        description=data.description,
        service=data.service,
        severity=IncidentSeverity(data.severity.upper()),
        status=IncidentStatus.OPEN,
        incident_time=datetime.fromisoformat(data.incident_time.replace("Z", "+00:00")) if data.incident_time else None,
        created_by=current_user.id,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    logger.info("incident.created", incident_id=incident.id, service=incident.service)
    return IncidentResponse(
        id=incident.id, title=incident.title, description=incident.description,
        service=incident.service, severity=incident.severity.value,
        status=incident.status.value,
        incident_time=incident.incident_time.isoformat() if incident.incident_time else None,
        created_at=incident.created_at.isoformat(),
        confidence_score=None,
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentResponse(
        id=incident.id, title=incident.title, description=incident.description,
        service=incident.service,
        severity=incident.severity.value if hasattr(incident.severity, "value") else incident.severity,
        status=incident.status.value if hasattr(incident.status, "value") else incident.status,
        incident_time=incident.incident_time.isoformat() if incident.incident_time else None,
        created_at=incident.created_at.isoformat(),
        confidence_score=incident.confidence_score,
    )


async def _run_investigation_background(incident_id: str):
    """Run the investigation graph in the background."""
    from app.workflows.investigation_graph import investigation_graph
    from app.workflows.state import InvestigationState, InvestigationStatus
    from app.core.database import AsyncSessionLocal

    logger.info("investigation.starting", incident_id=incident_id)

    async with AsyncSessionLocal() as db:
        # Get incident
        result = await db.execute(select(Incident).where(Incident.id == incident_id))
        incident = result.scalar_one_or_none()
        if not incident:
            logger.error("investigation.incident_not_found", incident_id=incident_id)
            return

        # Update status
        incident.status = IncidentStatus.INVESTIGATING
        await db.commit()

        # Build initial state
        initial_state = InvestigationState(
            incident_id=incident_id,
            incident_title=incident.title,
            incident_description=incident.description,
            incident_service=incident.service,
            incident_time=incident.incident_time.isoformat() if incident.incident_time else datetime.utcnow().isoformat(),
        )

        # Log event
        event = InvestigationEvent(
            id=str(uuid.uuid4()),
            incident_id=incident_id,
            agent_node="system",
            event_type=InvestigationEventType.INCIDENT_RECEIVED,
            summary=f"Investigation started for: {incident.title}",
        )
        db.add(event)
        await db.commit()

    # Run the graph
    try:
        final_state = await investigation_graph.ainvoke(initial_state)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Incident).where(Incident.id == incident_id))
            incident = result.scalar_one_or_none()
            if not incident:
                return

            # Persist results
            incident.status = IncidentStatus.RESOLVED
            incident.confidence_score = final_state.overall_confidence
            incident.final_report = final_state.final_report
            if final_state.incident_analysis:
                incident.analyzed_symptoms = final_state.incident_analysis.symptoms
                incident.analyzed_time_range = final_state.incident_analysis.time_range
            if final_state.investigation_plan:
                incident.investigation_plan = final_state.investigation_plan.model_dump()

            # Persist hypotheses
            for h in final_state.hypotheses:
                from app.models import Hypothesis as HypModel, HypothesisStatus
                hyp = HypModel(
                    id=str(uuid.uuid4()),
                    incident_id=incident_id,
                    hypothesis_id=h.id,
                    description=h.description,
                    status=HypothesisStatus(h.validation_status) if h.validation_status else HypothesisStatus.PENDING,
                    confidence_score=h.confidence_score,
                    rank=h.rank,
                    missing_evidence=h.missing_evidence,
                )
                db.add(hyp)

            # Persist evidence
            for ev in final_state.collected_evidence[:50]:  # Cap at 50
                from app.models import Evidence as EvModel, EvidenceSourceType
                try:
                    src_type = EvidenceSourceType(ev.source_type.upper())
                except ValueError:
                    src_type = EvidenceSourceType.LOG
                ev_model = EvModel(
                    id=str(uuid.uuid4()),
                    incident_id=incident_id,
                    source_type=src_type,
                    source_id=ev.source_id,
                    content=ev.content,
                    relevance_score=ev.relevance,
                    supports=ev.supports,
                    contradicts=ev.contradicts,
                )
                db.add(ev_model)

            # Persist recommendations
            for rec in final_state.recommendations:
                from app.models import Recommendation as RecModel, RiskLevel as DBRiskLevel, RecommendationStatus
                rec_model = RecModel(
                    id=str(uuid.uuid4()),
                    incident_id=incident_id,
                    action=rec.action,
                    reason=rec.reason,
                    risk_level=DBRiskLevel(rec.risk_level),
                    status=RecommendationStatus.PENDING,
                    expected_outcome=rec.expected_outcome,
                    potential_impact=rec.potential_impact,
                    rollback_strategy=rec.rollback_strategy,
                    supporting_evidence=rec.supporting_evidence,
                )
                db.add(rec_model)

            # Final event
            db.add(InvestigationEvent(
                id=str(uuid.uuid4()),
                incident_id=incident_id,
                agent_node="system",
                event_type=InvestigationEventType.REPORT_GENERATED,
                summary=f"Investigation complete. Confidence: {final_state.overall_confidence:.0f}/100",
            ))

            await db.commit()
            logger.info("investigation.complete", incident_id=incident_id, confidence=final_state.overall_confidence)

    except Exception as e:
        logger.error("investigation.failed", incident_id=incident_id, error=str(e))
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Incident).where(Incident.id == incident_id))
            incident = result.scalar_one_or_none()
            if incident:
                incident.status = IncidentStatus.OPEN
                db.add(InvestigationEvent(
                    id=str(uuid.uuid4()),
                    incident_id=incident_id,
                    event_type=InvestigationEventType.INVESTIGATION_FAILED,
                    summary=f"Investigation failed: {str(e)[:500]}",
                    error_message=str(e),
                    success=False,
                ))
                await db.commit()


@router.post("/{incident_id}/investigate")
async def start_investigation(
    incident_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger an investigation for an incident.
    Returns immediately — investigation runs in the background.
    Poll GET /{incident_id} to check status.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status == IncidentStatus.INVESTIGATING:
        raise HTTPException(status_code=409, detail="Investigation already in progress")

    background_tasks.add_task(_run_investigation_background, incident_id)

    return {
        "incident_id": incident_id,
        "status": "INVESTIGATING",
        "message": "Investigation started. Poll GET /incidents/{id} for status.",
    }


@router.get("/{incident_id}/events")
async def get_investigation_events(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InvestigationEvent)
        .where(InvestigationEvent.incident_id == incident_id)
        .order_by(InvestigationEvent.timestamp.asc())
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type.value if hasattr(e.event_type, "value") else e.event_type,
            "agent_node": e.agent_node,
            "tool_name": e.tool_name,
            "summary": e.summary,
            "success": e.success,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]


@router.get("/{incident_id}/hypotheses")
async def get_hypotheses(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Hypothesis).where(Hypothesis.incident_id == incident_id)
        .order_by(Hypothesis.rank.asc())
    )
    hypotheses = result.scalars().all()
    return [
        {
            "id": h.id,
            "hypothesis_id": h.hypothesis_id,
            "description": h.description,
            "status": h.status.value if hasattr(h.status, "value") else h.status,
            "confidence_score": h.confidence_score,
            "rank": h.rank,
            "missing_evidence": h.missing_evidence,
        }
        for h in hypotheses
    ]


@router.get("/{incident_id}/evidence")
async def get_evidence(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Evidence).where(Evidence.incident_id == incident_id)
        .order_by(Evidence.relevance_score.desc())
    )
    evidence = result.scalars().all()
    return [
        {
            "id": e.id,
            "source_type": e.source_type.value if hasattr(e.source_type, "value") else e.source_type,
            "source_id": e.source_id,
            "content": e.content,
            "relevance_score": e.relevance_score,
            "supports": e.supports,
            "contradicts": e.contradicts,
            "timestamp": e.evidence_timestamp.isoformat() if e.evidence_timestamp else None,
        }
        for e in evidence
    ]


@router.get("/{incident_id}/recommendations")
async def get_recommendations(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Recommendation).where(Recommendation.incident_id == incident_id)
    )
    recs = result.scalars().all()
    return [
        {
            "id": r.id,
            "action": r.action,
            "reason": r.reason,
            "risk_level": r.risk_level.value if hasattr(r.risk_level, "value") else r.risk_level,
            "status": r.status.value if hasattr(r.status, "value") else r.status,
            "expected_outcome": r.expected_outcome,
            "potential_impact": r.potential_impact,
            "rollback_strategy": r.rollback_strategy,
        }
        for r in recs
    ]
