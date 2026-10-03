"""
Services Package
=================
Business logic layer sitting between API routes and the database.

Usage:
    from app.services.incident_service import IncidentService
    from app.services.investigation_service import InvestigationService
"""

from app.services.incident_service import IncidentService
from app.services.investigation_service import InvestigationService

__all__ = ["IncidentService", "InvestigationService"]
