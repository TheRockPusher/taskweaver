"""Research agent - handles external data gathering."""

import json
from dataclasses import asdict

from pydantic_ai import RunContext
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

from .dependencies import TaskDependencies
from .github_issues import GitHubIssueSyncService
from .shared import create_agent
from .tools import require_write_access


def github_import_tool(ctx: RunContext[TaskDependencies], repo_names: list[str]) -> str:
    """Persist issues from explicitly supplied owner/repo repositories.

    Uses this request's task database, not cached global repository configuration.
    Imports and repeated pulls are durable; no remote writes are authorized here.
    API failures propagate so an unavailable repository is never reported as empty.
    """
    require_write_access(ctx)
    with GitHubIssueSyncService(ctx.deps.task_repo.db_path) as service:
        result = service.import_issues(repo_names)
    return json.dumps(asdict(result), indent=2, default=str)


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
