from operator import attrgetter

from github import Github
from github.Issue import Issue
from loguru import logger


def get_github_issues(repo_names: list[str]) -> list[dict]:
    g = Github()
    logger.debug("Starting github issues loading")
    issues: list[Issue] = [issue for repo in repo_names for issue in g.get_repo(repo).get_issues()]
    fields: list[str] = ["title", "body"]
    select_fields = attrgetter(*fields)
    result = [dict(zip(fields, select_fields(issue), strict=True)) for issue in issues]
    return result
