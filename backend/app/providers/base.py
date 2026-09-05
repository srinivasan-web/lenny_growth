from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


class ProviderError(Exception):
    """A provider-neutral, safe-to-return generation failure."""


@dataclass(frozen=True, slots=True)
class LLMRequest:
    system_prompt: str
    user_prompt: str
    temperature: float = 0.2
    max_output_tokens: int = 1_200
    model: str | None = None


@dataclass(frozen=True, slots=True)
class LLMGeneration:
    text: str
    provider: str
    model: str


class BaseLLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMGeneration:
        """Generate a complete text response."""

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Yield text deltas in their generation order."""


# Backward-compatible alias while application code adopts the explicit base name.
LLMProvider = BaseLLMProvider
