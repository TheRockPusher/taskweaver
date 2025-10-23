"""Github issues funtions."""

from operator import attrgetter

from github import Github
from github.Issue import Issue
from loguru import logger


def get_github_issues(repo_names: list[str]) -> list[dict]:
    """Fetch open GitHub issues from specified repositories.

    Retrieves all open issues from the provided GitHub repositories using
    unauthenticated access (rate-limited). Extracts issue title and body
    for use in task creation and prioritization.

    Args:
        repo_names: List of repository identifiers in format "owner/repo"
            (e.g., ["TheRockPusher/taskweaver", "torvalds/linux"]).

    Returns:
        List of dictionaries with keys "title" and "body" for each issue.
        Returns empty list if no issues found or repositories don't exist.

    Raises:
        github.UnknownObjectException: If a repository doesn't exist.
        github.RateLimitExceededException: If rate limit is exceeded.

    Example:
        >>> issues = get_github_issues(["TheRockPusher/taskweaver"])
        >>> print(issues[0]["title"])
        "Fix memory leak in WebSocket handler"
    """
    g = Github()
    logger.debug(f"Starting - github issues loading for repo {repo_names}")
    issues: list[Issue] = [issue for repo in repo_names for issue in g.get_repo(repo).get_issues()]
    logger.debug(f"{len(issues)} issues found")
    fields: list[str] = ["title", "body"]
    select_fields = attrgetter(*fields)
    result = [dict(zip(fields, select_fields(issue), strict=True)) for issue in issues]
    return result
