"""Shared prompt loading and request-time provider construction."""

# Provider imports must remain request-time so local CRUD needs no SDK credentials.
# ruff: noqa: PLC0415

import os
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import UserError
from pydantic_ai.models import Model

from ..config import get_config

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(filename: str) -> str:
    """Read a bundled prompt, raising FileNotFoundError for unknown names."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def get_model() -> Model:
    """Resolve current preferences only when AI is requested, never at import."""
    get_config.cache_clear()
    config = get_config()
    provider, separator, name = config.llm_model.partition(":")
    if not separator:
        provider, name = "openai", provider
    if provider == "offline":
        raise UserError("AI is disabled. Run 'taskweaver setup' to select a local or cloud provider.")
    if not name:
        raise UserError("The configured model is empty. Run 'taskweaver setup' to select a model.")
    endpoint = config.api_endpoint or None
    variables = {
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "google-genai": "GOOGLE_API_KEY",
        "local": "TASKWEAVER_API_KEY",
    }
    variable = variables.get(provider)
    if variable is None:
        raise UserError(
            f"Unsupported provider '{provider}'. Choose local, openai, openrouter, "
            "anthropic, or google-genai in 'taskweaver setup'."
        )
    key = os.environ.get(variable, "")
    from httpx import AsyncClient

    if provider == "local":
        if endpoint is None:
            raise UserError(
                "Local models require api_endpoint, for example http://localhost:11434/v1. Run 'taskweaver setup'."
            )
    elif not key.strip():
        raise UserError(f"{variable} is missing. Run 'taskweaver setup' or set {variable} before requesting AI.")
    if provider in {"local", "openai", "openrouter"}:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        if provider == "openrouter":
            endpoint = endpoint or "https://openrouter.ai/api/v1"
        elif provider == "openai":
            endpoint = endpoint or "https://api.openai.com/v1"
        # OpenAI 1.x honors an explicit empty key without cloud fallback or an
        # Authorization header. The package excludes incompatible SDK majors.
        return OpenAIChatModel(name, provider=OpenAIProvider(base_url=endpoint, api_key=key, http_client=AsyncClient()))
    if provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(
            name,
            provider=AnthropicProvider(
                api_key=key, base_url=endpoint or "https://api.anthropic.com", http_client=AsyncClient()
            ),
        )
    from google.genai import Client
    from google.genai.types import HttpOptions
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    options = HttpOptions(base_url=endpoint) if endpoint else None
    client = Client(api_key=key, vertexai=False, http_options=options)
    return GoogleModel(name, provider=GoogleProvider(client=client))


async def close_model(model: Model) -> None:
    """Close this turn's owned SDK transport before its event loop ends."""
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.models.openai import OpenAIChatModel

    if isinstance(model, (OpenAIChatModel, AnthropicModel)):
        await model.client.close()
    elif isinstance(model, GoogleModel):
        await model.client.aio.aclose()
        model.client.close()


def create_agent[D](prompt_name: str, tools: list, deps_type: type[D], **kwargs: Any) -> Agent[D, str]:  # noqa: ANN401
    """Create an unbound agent; callers supply a fresh model for every run."""
    # None follows Agent.instrument_all(), which is off until the CLI explicitly opts in.
    kwargs.setdefault("instrument", None)
    return Agent[D, str](
        model=None,
        deps_type=deps_type,
        instructions=load_prompt(f"{prompt_name}.md"),
        tools=tools,
        **kwargs,
    )
