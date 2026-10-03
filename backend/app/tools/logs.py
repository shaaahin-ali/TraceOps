"""
Log Search Tool
================
Searches application logs stored in PostgreSQL.

🎓 WHY NOT ELASTICSEARCH?
For the MVP, logs are stored in PostgreSQL.
This is simpler to run locally and sufficient for the controlled test environment.
The tool interface is the same regardless of backend — switching to Elasticsearch
later would only require changing this file, not the agent.
"""

from typing import Any
from datetime import datetime

from langchain_core.tools import tool
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import LogEntry


@tool
async def search_logs(
    service: str,
    start_time: str,
    end_time: str,
    keyword: str = "",
    severity: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """
    Search application log entries for a service within a time range.

    Args:
        service: Service name (e.g., 'payment-api', 'fraud-service')
        start_time: ISO 8601 start timestamp (e.g., '2026-09-06T10:00:00Z')
        end_time: ISO 8601 end timestamp (e.g., '2026-09-06T11:00:00Z')
        keyword: Optional keyword to filter log messages (case-insensitive)
        severity: Optional severity filter: INFO, WARN, ERROR
        limit: Maximum log entries to return (default 50, max 200)

    Returns:
        dict with 'logs' list and 'summary' statistics
    """
    try:
        limit = min(limit, 200)
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        async with AsyncSessionLocal() as db:
            query = select(LogEntry).where(
                and_(
                    LogEntry.service == service,
                    LogEntry.timestamp >= start_dt,
                    LogEntry.timestamp <= end_dt,
                )
            )
            if severity:
                query = query.where(LogEntry.level == severity.upper())
            if keyword:
                query = query.where(LogEntry.message.ilike(f"%{keyword}%"))

            query = query.order_by(LogEntry.timestamp.asc()).limit(limit)
            result = await db.execute(query)
            logs = result.scalars().all()

            log_list = [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat(),
                    "level": log.level,
                    "service": log.service,
                    "message": log.message,
                    "request_id": log.request_id,
                    "metadata": log.log_metadata,
                }
                for log in logs
            ]

            # Compute summary statistics
            levels = [l["level"] for l in log_list]
            summary = {
                "total": len(log_list),
                "errors": levels.count("ERROR"),
                "warnings": levels.count("WARN"),
                "info": levels.count("INFO"),
                "time_range": {"start": start_time, "end": end_time},
                "service": service,
            }

            # Detect patterns
            error_messages = [l["message"] for l in log_list if l["level"] == "ERROR"]
            if error_messages:
                summary["notable_errors"] = error_messages[:5]

            return {
                "success": True,
                "logs": log_list,
                "summary": summary,
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "logs": [],
            "summary": {"total": 0},
        }
