"""Chat model factory (gpt-4.1-mini on the Azure OpenAI-compatible endpoint)."""
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.errors import ModelNotConfiguredError


def make_chat_model(settings: Settings) -> ChatOpenAI:
    """Build the chat client from settings; the key is read only here and never logged."""
    if not settings.model_configured:
        raise ModelNotConfiguredError("chat model is not configured (check .env)")
    return ChatOpenAI(
        model=settings.chat_deployment,  # on Azure this is the deployment name
        base_url=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key.get_secret_value(),
        temperature=0,  # deterministic ranking and answers
        timeout=settings.model_timeout_seconds,
        max_retries=settings.model_max_retries,
    )
