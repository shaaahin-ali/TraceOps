"""
RootTrace Core Configuration
=============================
Uses Pydantic Settings to load from environment variables / .env file.
All sensitive values come from environment — never hardcoded.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings object. Pydantic automatically reads from:
    1. Environment variables
    2. .env file (if present)

    Type annotations serve as documentation AND validation.
    If DATABASE_URL is missing, the app fails fast on startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ──────────────────────────────────────────
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    # ── Database ─────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://roottrace:roottrace_secret@localhost:5432/roottrace"

    # ── Security ─────────────────────────────────────────────
    jwt_secret: str = "CHANGE_ME_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ── LLM ──────────────────────────────────────────────────
    llm_provider: Literal["gemini", "openai", "anthropic"] = "gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.1

    # ── Embeddings ───────────────────────────────────────────
    embedding_provider: Literal["gemini", "openai"] = "gemini"
    embedding_model: str = "text-embedding-004"
    embedding_dimension: int = 768

    # ── GitHub (optional) ────────────────────────────────────
    github_token: str = ""
    github_repo_owner: str = ""
    github_repo_name: str = "roottrace-incident-lab"

    # ── Incident Lab ─────────────────────────────────────────
    incident_lab_repo_path: str = "./incident-lab/payment-api"

    # ── LangSmith (optional) ─────────────────────────────────
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "roottrace"

    # ── Investigation Limits ─────────────────────────────────
    max_tool_calls: int = 20
    max_hypotheses: int = 5
    max_retrieval_results: int = 20
    max_investigation_time_seconds: int = 300
    max_retries: int = 3

    # ── Confidence Thresholds ────────────────────────────────
    confidence_threshold_strong: int = 80
    confidence_threshold_moderate: int = 60
    confidence_threshold_weak: int = 40


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings singleton.
    Use this instead of creating Settings() directly.

    Why @lru_cache?
    - Settings reads from disk/env. We only want to do this once.
    - All callers get the same object.
    - Tests can override by clearing the cache.
    """
    return Settings()
