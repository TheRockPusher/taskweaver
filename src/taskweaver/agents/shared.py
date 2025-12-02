"""Shared utilities for agents - composition pattern."""

from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from ..config import get_config

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(filename: str) -> str:
    """Load prompt from markdown file.

    Args:
        filename: Prompt filename (e.g., "task.md")

    Returns:
        Prompt content as string.

    Raises:
        FileNotFoundError: If prompt file doesn't exist.
    """
    prompt_path = PROMPTS_DIR / filename
    return prompt_path.read_text(encoding="utf-8")


def get_model_name() -> str:
    """Get model name with provider prefix.

    Returns:
        Model name (e.g., "openai:gpt-4o-mini")
    """
    config = get_config()
    model = config.llm_model
    return model if ":" in model else f"openai:{model}"


def create_agent[D](
    prompt_name: str,
    tools: list,
    deps_type: type[D],
    **kwargs: Any,  # noqa: ANN401
) -> Agent[D, str]:
    """Factory to create agents - composition pattern.

    Args:
        prompt_name: Prompt filename without .md extension
        tools: List of tool functions
        deps_type: Dependency type for RunContext
        **kwargs: Additional Agent() parameters

    Returns:
        Configured Agent instance with str result type.

    Example:
        >>> agent = create_agent("task", task_tools, TaskDependencies)
    """
    return Agent[D, str](
        get_model_name(),
        deps_type=deps_type,
        system_prompt=load_prompt(f"{prompt_name}.md"),
        tools=tools,
        defer_model_check=True,
        instrument=True,
        **kwargs,
    )
