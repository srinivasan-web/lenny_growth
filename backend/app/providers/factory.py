from app.config import Settings, get_settings
from app.providers.base import BaseLLMProvider, ProviderError
from app.providers.cloud_provider import CloudProvider
from app.providers.ollama_provider import OllamaProvider


def get_llm_provider(settings: Settings | None = None) -> BaseLLMProvider:
    settings = settings or get_settings()
    provider_name = settings.default_llm_provider.lower()

    if provider_name in {"cloud", "openai"}:
        if settings.cloud_provider.lower() != "openai":
            raise ProviderError(f"Unsupported cloud provider: {settings.cloud_provider}.")
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        return CloudProvider(
            api_key=api_key,
            default_model=settings.openai_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            default_model=settings.ollama_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise ProviderError(f"Unsupported LLM provider: {provider_name}.")
