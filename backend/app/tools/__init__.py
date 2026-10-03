"""
RootTrace Investigation Tools
================================
All 7 tools that the LangGraph agent can call during investigation.

🎓 DESIGN PRINCIPLES:
1. Each tool returns structured data, not raw strings
2. Tools never fail silently — they return error status with partial data
3. Tools do NOT have shell injection risk — no string interpolation in SQL
4. Tools are registered with LangChain's @tool decorator for LangGraph
5. The agent receives tool schemas from these decorators automatically

🎓 TOOL SECURITY:
- All SQL uses parameterized queries (SQLAlchemy text() with bound params)
- Git operations use subprocess with argument arrays, no shell=True
- File paths are validated against the known repo root
- No user input reaches shell execution
"""

from app.tools.logs import search_logs
from app.tools.metrics import search_metrics
from app.tools.deployments import search_deployments
from app.tools.git import search_commits, get_commit_diff, search_files
from app.tools.knowledge_base import search_knowledge_base
from app.tools.incidents import search_historical_incidents

__all__ = [
    "search_logs",
    "search_metrics",
    "search_deployments",
    "search_commits",
    "get_commit_diff",
    "search_files",
    "search_knowledge_base",
    "search_historical_incidents",
]

ALL_TOOLS = [
    search_logs,
    search_metrics,
    search_deployments,
    search_commits,
    get_commit_diff,
    search_files,
    search_knowledge_base,
    search_historical_incidents,
]
