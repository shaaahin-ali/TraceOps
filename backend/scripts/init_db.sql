-- RootTrace PostgreSQL Initialization
-- Enables the pgvector extension before migrations run
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for keyword/fuzzy search
