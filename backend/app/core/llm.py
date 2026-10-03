"""
LLM Provider Abstraction
=========================
Abstracts LLM calls behind a clean interface.
Switching providers requires only changing the LLM_PROVIDER env var.

🎓 WHY ABSTRACT THE LLM?
If we call langchain_google_genai directly throughout the codebase,
switching to OpenAI means changing dozens of import statements.
The abstraction means every agent node just calls llm.generate() or
llm.generate_structured() — the provider is irrelevant to the node logic.

🎓 STRUCTURED OUTPUT:
generate_structured() uses LangChain's .with_structured_output() to
get back a Pydantic model instead of a string. This is critical for:
- IncidentAnalysis (structured JSON from free-text incident)
- Hypothesis generation (list of Hypothesis objects)
- Validation results (enum values, not strings)
"""

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Type, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.core.config import get_settings

settings = get_settings()
T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """Interface all LLM providers must implement."""

    @abstractmethod
    def get_model(self) -> BaseChatModel:
        """Return the underlying LangChain chat model."""

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a text response."""
        model = self.get_model()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await model.ainvoke(messages)
        return response.content

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
    ) -> T:
        """
        Generate a structured response conforming to a Pydantic schema.
        Retries once on failure before raising.
        """
        model = self.get_model()
        structured_model = model.with_structured_output(output_schema)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        try:
            return await structured_model.ainvoke(messages)
        except Exception as first_error:
            # One retry with simplified prompt
            try:
                simplified_prompt = (
                    f"{user_prompt}\n\n"
                    "IMPORTANT: Respond ONLY with a valid JSON object matching the required schema. "
                    "Do not include any additional text."
                )
                messages[1] = HumanMessage(content=simplified_prompt)
                return await structured_model.ainvoke(messages)
            except Exception:
                raise first_error


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini via LangChain."""

    def get_model(self) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.gemini_api_key,
            temperature=settings.llm_temperature,
            convert_system_message_to_human=False,
        )


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI GPT via LangChain."""

    def get_model(self) -> BaseChatModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
        )


class AnthropicLLMProvider(BaseLLMProvider):
    """Anthropic Claude via LangChain."""

    def get_model(self) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            temperature=settings.llm_temperature,
        )


@lru_cache(maxsize=1)
def get_llm_provider() -> BaseLLMProvider:
    """Factory — returns configured LLM provider, cached."""
    provider = settings.llm_provider
    if provider == "gemini":
        return GeminiLLMProvider()
    elif provider == "openai":
        return OpenAILLMProvider()
    elif provider == "anthropic":
        return AnthropicLLMProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
