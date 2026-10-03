"""
Knowledge Base Ingestion Script
=================================
Loads all documents from incident-lab/knowledge-base/ into PostgreSQL with pgvector.

Pipeline:
    Documents (Markdown files)
        ↓ load
        ↓ parse structure (headings, sections)
        ↓ chunk (structure-aware)
        ↓ extract metadata
        ↓ embed (Gemini text-embedding-004)
        ↓ store in document_chunks with vector

🎓 STRUCTURE-AWARE CHUNKING:
Instead of splitting at arbitrary character limits (which breaks logic mid-sentence),
we split at heading boundaries. Each chunk is a complete section of the document.
This preserves the meaning of runbook procedures and postmortem sections.

Run: python scripts/ingest_knowledge_base.py
"""

import asyncio
import hashlib
import os
import sys
from pathlib import Path
from typing import Iterator

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from app.retrieval.embeddings import get_embedding_provider

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://roottrace:roottrace_secret@localhost:5432/roottrace"
)

KB_ROOT = Path(__file__).parent.parent.parent / "incident-lab" / "knowledge-base"

# Document type mapping by directory
DIR_TO_TYPE = {
    "architecture": "architecture",
    "api-docs": "api_docs",
    "runbooks": "runbook",
    "troubleshooting": "troubleshooting",
    "postmortems": "postmortem",
    "historical-incidents": "historical_incident",
}

# Service keywords for auto-detection
SERVICE_KEYWORDS = {
    "payment-api": ["payment", "payments", "payment-api"],
    "fraud-service": ["fraud", "fraud-service"],
    "auth": ["auth", "authentication", "jwt"],
    "database": ["database", "postgres", "postgresql", "db"],
}


def detect_service(content: str, filename: str) -> str:
    """Detect which service a document is about."""
    text_lower = (content + " " + filename).lower()
    for service, keywords in SERVICE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return service
    return ""


def extract_section_metadata(heading: str, content: str) -> dict:
    """Extract structured metadata from a markdown section."""
    return {
        "section": heading.strip("#").strip(),
        "has_code": "```" in content,
        "has_table": "|" in content,
        "char_count": len(content),
    }


def chunk_markdown(content: str, doc_metadata: dict) -> list[dict]:
    """
    Structure-aware chunking: split on level-2 headings (##).
    Each chunk = one logical section of the document.
    Minimum chunk size: 50 characters.
    """
    chunks = []
    lines = content.split("\n")
    current_heading = doc_metadata.get("name", "Introduction")
    current_lines: list[str] = []
    chunk_index = 0

    def flush_chunk():
        nonlocal chunk_index
        text = "\n".join(current_lines).strip()
        if len(text) >= 50:
            section_meta = extract_section_metadata(current_heading, text)
            chunks.append({
                "content": text,
                "chunk_index": chunk_index,
                "metadata": {
                    **doc_metadata,
                    **section_meta,
                }
            })
            chunk_index += 1

    for line in lines:
        if line.startswith("## ") or line.startswith("# "):
            flush_chunk()
            current_heading = line
            current_lines = [line]
        else:
            current_lines.append(line)

    flush_chunk()  # Last section
    return chunks


async def ingest_file(db, embedding_provider, file_path: Path, doc_type: str) -> int:
    """Ingest a single markdown file. Returns number of chunks created."""
    content = file_path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Check if already ingested (by hash)
    existing = await db.execute(
        text("SELECT id FROM documents WHERE content_hash = :hash"),
        {"hash": content_hash}
    )
    if existing.scalar_one_or_none():
        print(f"    ⏭  Skipping (unchanged): {file_path.name}")
        return 0

    service = detect_service(content, file_path.name)

    # Upsert document record
    doc_id = hashlib.md5(str(file_path).encode()).hexdigest()
    await db.execute(text("""
        INSERT INTO documents (id, name, document_type, service, file_path, content_hash, created_at, updated_at)
        VALUES (:id, :name, :doc_type, :service, :file_path, :content_hash, NOW(), NOW())
        ON CONFLICT (id) DO UPDATE SET
            content_hash = EXCLUDED.content_hash,
            updated_at = NOW()
    """), {
        "id": doc_id,
        "name": file_path.stem,
        "doc_type": doc_type,
        "service": service,
        "file_path": str(file_path),
        "content_hash": content_hash,
    })

    # Delete old chunks for this document (if re-ingesting)
    await db.execute(
        text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
        {"doc_id": doc_id}
    )

    # Chunk the document
    doc_metadata = {
        "name": file_path.stem,
        "document_type": doc_type,
        "service": service,
        "file": file_path.name,
    }
    chunks = chunk_markdown(content, doc_metadata)

    # Embed and store each chunk
    for chunk in chunks:
        embedding = await embedding_provider.embed(chunk["content"])
        import json
        import uuid
        await db.execute(text("""
            INSERT INTO document_chunks (id, document_id, content, embedding, chunk_metadata, chunk_index, created_at)
            VALUES (:id, :doc_id, :content, CAST(:embedding AS vector), :metadata::jsonb, :idx, NOW())
        """), {
            "id": str(uuid.uuid4()),
            "doc_id": doc_id,
            "content": chunk["content"],
            "embedding": "[" + ",".join(str(x) for x in embedding) + "]",
            "metadata": json.dumps(chunk["metadata"]),
            "idx": chunk["chunk_index"],
        })

    await db.commit()
    return len(chunks)


async def main():
    print("\n📚 RootTrace Knowledge Base Ingestion\n")
    print(f"Source: {KB_ROOT}\n")

    if not KB_ROOT.exists():
        print(f"ERROR: Knowledge base directory not found: {KB_ROOT}")
        sys.exit(1)

    embedding_provider = get_embedding_provider()
    print(f"Embedding provider: {type(embedding_provider).__name__}")
    print(f"Embedding dimension: {embedding_provider.dimension}\n")

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    total_chunks = 0
    total_files = 0

    async with async_session() as db:
        for dir_name, doc_type in DIR_TO_TYPE.items():
            dir_path = KB_ROOT / dir_name
            if not dir_path.exists():
                continue

            md_files = list(dir_path.glob("*.md"))
            if not md_files:
                continue

            print(f"📁 {dir_name}/ ({len(md_files)} files)")
            for file_path in sorted(md_files):
                print(f"    📄 {file_path.name}")
                n = await ingest_file(db, embedding_provider, file_path, doc_type)
                total_chunks += n
                total_files += 1
                if n:
                    print(f"       → {n} chunks embedded")

    await engine.dispose()
    print(f"\n✅ Ingestion complete!")
    print(f"   Files processed: {total_files}")
    print(f"   Chunks created: {total_chunks}")

    # Create pgvector index for fast similarity search
    print("\n⚡ Creating pgvector HNSW index...")
    idx_engine = create_async_engine(DATABASE_URL, echo=False)
    async with idx_engine.connect() as conn:
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding
            ON document_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """))
        await conn.commit()
    await idx_engine.dispose()
    print("✅ HNSW index created for fast vector search\n")


if __name__ == "__main__":
    asyncio.run(main())
