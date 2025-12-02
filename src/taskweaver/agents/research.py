"""Research agent - handles external data gathering."""

import json

from pydantic_ai import RunContext
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

from ..config import get_config
from .dependencies import TaskDependencies
from .github_issues import get_github_issues
from .shared import create_agent


def github_import_tool(_ctx: RunContext[TaskDependencies]) -> str:
    """Import open issues from configured GitHub repositories.

    Fetches issues from repositories configured in config.toml.
    Returns issues as JSON for the agent to process.

    Args:
        _ctx: Runtime context (unused but required for tool signature)

    Returns:
        JSON string of GitHub issues with metadata.
    """
    config = get_config()
    if not config.github_repos:
        return "No GitHub repositories configured. Set github_repos in config.toml."

    issues = get_github_issues(config.github_repos)
    if not issues:
        return "No open issues found in configured repositories."

    return json.dumps(issues, indent=2, default=str)


# Research tools
RESEARCH_TOOLS = [
    duckduckgo_search_tool(),
    github_import_tool,
]

# Create ResearchAgent using factory (composition!)
research_agent = create_agent(
    prompt_name="research",
    tools=RESEARCH_TOOLS,
    deps_type=TaskDependencies,
)
