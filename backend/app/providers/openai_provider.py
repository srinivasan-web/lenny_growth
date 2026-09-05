from collections.abc import AsyncIterator

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAIError

from app.providers.base import BaseLLMProvider, LLMGeneration, LLMRequest, ProviderError


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def __init__(self, *, api_key: str, default_model: str, timeout_seconds: float) -> None:
        if not api_key:
            raise ProviderError("OpenAI is selected but OPENAI_API_KEY is not configured.")
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)
        self._default_model = default_model

    async def generate(self, request: LLMRequest) -> LLMGeneration:
        model = request.model or self._default_model
        try:
            response = await self._client.responses.create(
                model=model,
                instructions=request.system_prompt,
                input=request.user_prompt,
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                store=False,
            )
        except (APIConnectionError, APITimeoutError) as error:
            raise ProviderError("OpenAI is unavailable or timed out.") from error
        except APIStatusError as error:
            raise ProviderError(f"OpenAI request failed with status {error.status_code}.") from error
        except OpenAIError as error:
            raise ProviderError("OpenAI generation failed.") from error
        except Exception as error:
            raise ProviderError("OpenAI generation failed.") from error

        if not response.output_text:
            raise ProviderError("OpenAI returned no text output.")
        return LLMGeneration(text=response.output_text, provider=self.name, model=model)

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        model = request.model or self._default_model
        try:
            stream = await self._client.responses.create(
                model=model,
                instructions=request.system_prompt,
                input=request.user_prompt,
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                store=False,
                stream=True,
            )
            async for event in stream:
                if event.type == "response.output_text.delta":
                    yield event.delta
        except (APIConnectionError, APITimeoutError) as error:
            raise ProviderError("OpenAI is unavailable or timed out.") from error
        except APIStatusError as error:
            raise ProviderError(f"OpenAI request failed with status {error.status_code}.") from error
        except OpenAIError as error:
            raise ProviderError("OpenAI generation failed.") from error
        except Exception as error:
            raise ProviderError("OpenAI generation failed.") from error
