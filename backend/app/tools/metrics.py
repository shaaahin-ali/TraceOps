"""
Metrics Search Tool
====================
Queries time-series metric data from PostgreSQL.

Returns raw values AND computed statistics (min, max, avg, spike detection).
The agent uses spike detection to identify anomalies without having to
do the math itself.
"""

from typing import Any
from datetime import datetime
import statistics

from langchain_core.tools import tool
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Metric


@tool
async def search_metrics(
    service: str,
    metric_name: str,
    start_time: str,
    end_time: str,
) -> dict[str, Any]:
    """
    Search time-series metrics for a service within a time range.

    Args:
        service: Service name (e.g., 'payment-api', 'fraud-service')
        metric_name: Metric to query. Available metrics:
                     api_latency_ms, error_rate, cpu_percent, memory_percent,
                     db_connections, db_query_latency_ms, request_count,
                     response_latency_ms (for fraud-service)
        start_time: ISO 8601 start timestamp
        end_time: ISO 8601 end timestamp

    Returns:
        dict with 'data_points' list, 'statistics', and 'anomalies'
    """
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Metric)
                .where(
                    and_(
                        Metric.service == service,
                        Metric.metric_name == metric_name,
                        Metric.timestamp >= start_dt,
                        Metric.timestamp <= end_dt,
                    )
                )
                .order_by(Metric.timestamp.asc())
            )
            metrics = result.scalars().all()

            if not metrics:
                return {
                    "success": True,
                    "data_points": [],
                    "statistics": None,
                    "anomalies": [],
                    "message": f"No data found for {service}/{metric_name} in time range",
                }

            values = [m.value for m in metrics]
            data_points = [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "value": m.value,
                }
                for m in metrics
            ]

            # Statistics
            avg = statistics.mean(values)
            std = statistics.stdev(values) if len(values) > 1 else 0
            stats = {
                "min": min(values),
                "max": max(values),
                "avg": round(avg, 2),
                "std_dev": round(std, 2),
                "count": len(values),
                "first": values[0],
                "last": values[-1],
                "change_pct": round(((values[-1] - values[0]) / values[0]) * 100, 1) if values[0] != 0 else 0,
            }

            # Spike detection: flag values > 2 standard deviations from mean
            spike_threshold = avg + (2 * std)
            anomalies = [
                {
                    "timestamp": data_points[i]["timestamp"],
                    "value": v,
                    "deviation_from_avg": round(v - avg, 2),
                }
                for i, v in enumerate(values)
                if v > spike_threshold and std > 0
            ]

            return {
                "success": True,
                "service": service,
                "metric_name": metric_name,
                "data_points": data_points,
                "statistics": stats,
                "anomalies": anomalies,
                "spike_detected": len(anomalies) > 0,
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data_points": [],
            "statistics": None,
            "anomalies": [],
        }
