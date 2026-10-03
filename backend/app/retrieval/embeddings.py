"""
Embedding Provider Abstraction
================================
Abstracts the embedding API behind a simple interface.
Switching from Gemini to OpenAI requires changing only this file.

🎓 WHY ABSTRACTION?
Hard-coding `import google.generativeai` throughout the codebase
means switching providers requires touching dozens of files.
The abstraction means the rest of the code just calls embed().

Current implementation: Google text-embedding-004 (768 dimensions)
"""

import asyncio
from abc import ABC, abstractmethod
from functools import lru_cache

import google.generativeai as genai

from app.core.config import get_settings

settings = get_settings()


class BaseEmbeddingProvider(ABC):
    """Interface all embedding providers must implement."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple texts."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Google Gemini text-embedding-004.
    Dimension: 768
    Max tokens: 2048
    """

    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self._model = settings.embedding_model  # text-embedding-004

    async def embed(self, text: str) -> list[float]:
        """Embed a single text asynchronously."""
        # Run the sync Gemini API in a thread pool to not block the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model=f"models/{self._model}",
                content=text,
                task_type="retrieval_document",
            )
        )
        return result["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Runs sequentially to avoid rate limits."""
        embeddings = []
        for text in texts:
            emb = await self.embed(text)
            embeddings.append(emb)
        return embeddings

    @property
    def dimension(self) -> int:
        return 768


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    OpenAI text-embedding-3-small.
    Dimension: 1536
    """

    def __init__(self):
        import openai
        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = "text-embedding-3-small"

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return 1536


@lru_cache(maxsize=1)
def get_embedding_provider() -> BaseEmbeddingProvider:
    """
    Factory function — returns the configured embedding provider.
    Cached so we create the provider once.
    """
    provider = settings.embedding_provider
    if provider == "gemini":
        return GeminiEmbeddingProvider()
    elif provider == "openai":
        return OpenAIEmbeddingProvider()
    else:
        raise ValueError(f"Unknown embedding provider: {provider!r}")
