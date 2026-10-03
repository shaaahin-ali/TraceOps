"""
Historical Incident Search Tool
=================================
Searches historical incidents and postmortems using semantic similarity.

🎓 WHY HISTORICAL INCIDENTS MATTER:
If a similar incident happened before, the agent can:
1. Confirm symptom patterns match
2. See what the root cause was previously
3. Use previous remediation as guidance
4. Increase confidence in current hypothesis

Historical incidents in the knowledge base are NOT the same as
the incidents being investigated. They are from the past.
The agent uses similarity — not exact matching.
"""

from typing import Any

from langchain_core.tools import tool

from app.core.database import AsyncSessionLocal
from app.retrieval.embeddings import get_embedding_provider
from sqlalchemy import text


@tool
async def search_historical_incidents(
    symptoms: list[str],
    service: str = "",
    top_k: int = 3,
) -> dict[str, Any]:
    """
    Search historical incidents and postmortems for similar patterns.

    Uses semantic similarity to find past incidents with matching symptoms.
    Returns past incidents with their root causes and resolutions.

    Args:
        symptoms: List of symptom descriptions
                  (e.g., ['high API latency', 'database connection timeout'])
        service: Optional service filter (e.g., 'payment-api')
        top_k: Number of similar incidents to return (default 3)

    Returns:
        dict with 'incidents' list with similarity scores and root causes
    """
    try:
        # Combine symptoms into a search query
        query = f"service {service} symptoms: " + "; ".join(symptoms)
        embedding_provider = get_embedding_provider()
        query_embedding = await embedding_provider.embed(query)

        async with AsyncSessionLocal() as db:
            # Search in postmortem and historical_incident document types
            sql = text("""
                SELECT
                    dc.id,
                    dc.content,
                    dc.chunk_metadata,
                    d.name as document_name,
                    d.document_type,
                    d.service,
                    1 - (dc.embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE d.document_type IN ('postmortem', 'historical_incident')
                AND dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
            """)

            vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            result = await db.execute(sql, {"embedding": vector_str, "limit": top_k * 3})
            rows = result.fetchall()

            # Group by document and take best chunk per document
            doc_best: dict[str, dict] = {}
            for row in rows:
                doc_name = row.document_name
                sim = float(row.similarity or 0)
                if doc_name not in doc_best or sim > doc_best[doc_name]["similarity_score"]:
                    doc_best[doc_name] = {
                        "document_name": doc_name,
                        "document_type": row.document_type,
                        "service": row.service,
                        "content_excerpt": row.content[:500],
                        "metadata": row.chunk_metadata,
                        "similarity_score": round(sim, 4),
                    }

            incidents = sorted(doc_best.values(), key=lambda x: x["similarity_score"], reverse=True)[:top_k]

            return {
                "success": True,
                "query_symptoms": symptoms,
                "incidents": incidents,
                "count": len(incidents),
                "note": "High similarity (>0.8) suggests a very similar past incident pattern",
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "incidents": [],
            "count": 0,
        }
