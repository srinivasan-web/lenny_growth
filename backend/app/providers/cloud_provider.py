from app.providers.openai_provider import OpenAIProvider


class CloudProvider(OpenAIProvider):
    """Cloud-provider boundary; currently implemented with the OpenAI Responses API."""

