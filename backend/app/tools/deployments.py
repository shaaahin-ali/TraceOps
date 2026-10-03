"""
Deployment Search Tool
========================
Searches deployment records for a service.

This tool helps the agent identify:
- What was deployed near the incident time
- Which commit SHA was deployed
- Whether the deployment preceded the incident
"""

from typing import Any
from datetime import datetime

from langchain_core.tools import tool
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Deployment


@tool
async def search_deployments(
    service: str,
    start_time: str,
    end_time: str,
) -> dict[str, Any]:
    """
    Search deployment records for a service within a time range.

    Args:
        service: Service name (e.g., 'payment-api')
        start_time: ISO 8601 start timestamp — look before incident time
        end_time: ISO 8601 end timestamp — look after incident time

    Returns:
        dict with 'deployments' list ordered by time (most recent first)
    """
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Deployment)
                .where(
                    and_(
                        Deployment.service == service,
                        Deployment.deployed_at >= start_dt,
                        Deployment.deployed_at <= end_dt,
                    )
                )
                .order_by(Deployment.deployed_at.desc())
            )
            deployments = result.scalars().all()

            dep_list = [
                {
                    "deployment_id": d.id,
                    "service": d.service,
                    "version": d.version,
                    "commit_sha": d.commit_sha,
                    "status": d.status,
                    "deployed_at": d.deployed_at.isoformat(),
                    "deployed_by": d.deployed_by,
                    "metadata": d.deployment_metadata,
                }
                for d in deployments
            ]

            return {
                "success": True,
                "deployments": dep_list,
                "count": len(dep_list),
                "service": service,
                "note": "Deployments immediately before an incident are high-priority investigation targets"
                if dep_list else "No deployments found in time range",
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "deployments": [],
            "count": 0,
        }
