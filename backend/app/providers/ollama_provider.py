import json
from collections.abc import AsyncIterator

import httpx

from app.providers.base import BaseLLMProvider, LLMGeneration, LLMRequest, ProviderError


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def __init__(self, *, base_url: str, default_model: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout_seconds = timeout_seconds

    def _payload(self, request: LLMRequest, stream: bool) -> dict[str, object]:
        return {
            "model": request.model or self._default_model,
            "system": request.system_prompt,
            "prompt": request.user_prompt,
            "stream": stream,
            "options": {"temperature": request.temperature, "num_predict": request.max_output_tokens},
        }

    async def generate(self, request: LLMRequest) -> LLMGeneration:
        model = request.model or self._default_model
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(f"{self._base_url}/api/generate", json=self._payload(request, False))
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise ProviderError("Ollama timed out.") from error
        except httpx.HTTPError as error:
            raise ProviderError("Ollama is unavailable or rejected the request.") from error

        text = response.json().get("response")
        if not isinstance(text, str) or not text:
            raise ProviderError("Ollama returned no text output.")
        return LLMGeneration(text=text, provider=self.name, model=model)

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                async with client.stream("POST", f"{self._base_url}/api/generate", json=self._payload(request, True)) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        payload = json.loads(line)
                        delta = payload.get("response")
                        if isinstance(delta, str) and delta:
                            yield delta
        except json.JSONDecodeError as error:
            raise ProviderError("Ollama returned malformed streaming data.") from error
        except httpx.TimeoutException as error:
            raise ProviderError("Ollama timed out.") from error
        except httpx.HTTPError as error:
            raise ProviderError("Ollama is unavailable or rejected the request.") from error
