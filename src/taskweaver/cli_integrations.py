"""Explicit user memory and durable GitHub synchronization commands."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .cli_planning import DB, command_errors, resolve_db
from .config import get_config

if TYPE_CHECKING:
    from .agents.github_issues import SyncResult
    from .agents.memory import MemoryFact, MemoryService

console = Console()
memory = typer.Typer(help="Manage explicit per-user facts; semantic storage is opt-in")
github = typer.Typer(help="Import GitHub issues and synchronize mapped tasks")


class MemoryCategory(str, Enum):
    """Explicit supported memory categories."""

    PREFERENCE = "preference"
    SKILL = "skill"
    GOAL = "goal"
    CONTEXT = "context"


class IssueState(str, Enum):
    """GitHub issue import states."""

    OPEN = "open"
    CLOSED = "closed"
    ALL = "all"


@memory.callback()
def memory_options(
    ctx: typer.Context,
    user: Annotated[str | None, typer.Option(help="Override configured user identity")] = None,
) -> None:
    """Select the configured user or an explicit identity for this command group."""
    ctx.obj = {"user": user if user is not None else get_config().user_id}


@contextmanager
def memory_service(ctx: typer.Context, db_path: DB, *, semantic: bool = False) -> Iterator["MemoryService"]:
    """Own the optional backend for precisely one command and always close it."""
    from .agents.memory import MemoryService  # noqa: PLC0415
    from .database.connection import close_mem0_memory, mem0_memory  # noqa: PLC0415

    config = get_config()
    if semantic and not config.memory_enabled:
        raise ValueError("Semantic memory is disabled; enable memory_enabled in configuration first")
    selected_db = resolve_db(ctx, db_path)
    backend = mem0_memory(config.model_copy(update={"database_file": selected_db})) if config.memory_enabled else None
    try:
        yield MemoryService(selected_db, user_id=ctx.obj["user"], semantic_backend=backend)
    finally:
        if backend is not None:
            close_mem0_memory(backend)


def _expiry(value: str | None) -> datetime | None:
    if value is None:
        return None
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Memory expiry must include a timezone (for example 2030-01-01T00:00:00+00:00)")
    return result


def _print_facts(facts: list["MemoryFact"]) -> None:
    table = Table(title="Explicit memory facts")
    for name in ("Key", "Value", "Category", "Version", "Expires"):
        table.add_column(name)
    for fact in facts:
        table.add_row(
            Text(fact.key),
            Text(fact.value),
            fact.category,
            str(fact.version),
            fact.expires_at.isoformat() if fact.expires_at else "Never",
        )
    console.print(table)


@memory.command(name="remember")
def remember(
    ctx: typer.Context,
    key: str,
    value: str,
    category: MemoryCategory = MemoryCategory.PREFERENCE,
    expires: str | None = None,
    db_path: DB = None,
) -> None:
    """Store or replace an explicit fact, optionally expiring at an ISO timestamp."""
    with command_errors(), memory_service(ctx, db_path) as service:
        fact = service.remember(key, value, category.value, _expiry(expires))
        _print_facts([fact])


@memory.command(name="update")
def update_memory(
    ctx: typer.Context,
    key: str,
    value: str,
    category: MemoryCategory = MemoryCategory.PREFERENCE,
    expires: str | None = None,
    db_path: DB = None,
) -> None:
    """Explicitly replace a fact; older versions cannot reappear in retrieval."""
    with command_errors(), memory_service(ctx, db_path) as service:
        fact = service.update(key, value, category.value, _expiry(expires))
        _print_facts([fact])


@memory.command(name="list")
def list_memories(ctx: typer.Context, category: MemoryCategory | None = None, db_path: DB = None) -> None:
    """List only current, unexpired facts for this user."""
    with command_errors(), memory_service(ctx, db_path) as service:
        _print_facts(service.list_facts(category.value if category else None))


@memory.command(name="search")
def search_memories(
    ctx: typer.Context, query: str, limit: Annotated[int, typer.Option(min=0)] = 10, db_path: DB = None
) -> None:
    """Search current authoritative facts locally and through optional semantic IDs."""
    with command_errors(), memory_service(ctx, db_path) as service:
        _print_facts(service.search(query, limit))


@memory.command(name="forget")
def forget_memory(ctx: typer.Context, key: str, db_path: DB = None) -> None:
    """Remove an explicit fact and suppress obsolete semantic versions."""
    with command_errors(), memory_service(ctx, db_path) as service:
        if not service.forget(key):
            raise ValueError(f"Memory not found for this user: {key}")
        console.print(f"Forgot {key}", markup=False)


@memory.command(name="expire")
def expire_memories(ctx: typer.Context, db_path: DB = None) -> None:
    """Purge expired facts for this user, retaining deletion tombstones."""
    with command_errors(), memory_service(ctx, db_path) as service:
        console.print(f"Expired {service.purge_expired()} fact(s)")


@memory.command(name="semantic-list")
def list_semantic(ctx: typer.Context, db_path: DB = None) -> None:
    """List provider memory IDs for deliberate correction/removal (requires opt-in)."""
    with command_errors(), memory_service(ctx, db_path, semantic=True) as service:
        table = Table(title="Semantic memory IDs")
        table.add_column("ID")
        table.add_column("Value")
        for record in service.list_semantic():
            table.add_row(Text(record.id), Text(record.value))
        console.print(table)


@memory.command(name="semantic-forget")
def forget_semantic(ctx: typer.Context, identifier: str, db_path: DB = None) -> None:
    """Remove one user-owned semantic ID (requires opt-in)."""
    with command_errors(), memory_service(ctx, db_path, semantic=True) as service:
        if not service.forget_semantic(identifier):
            raise ValueError("Semantic memory is not visible to this user")
        console.print(f"Forgot semantic memory {identifier}", markup=False)


@memory.command(name="semantic-update")
def correct_semantic(
    ctx: typer.Context,
    identifier: str,
    key: str,
    value: str,
    category: MemoryCategory = MemoryCategory.PREFERENCE,
    expires: str | None = None,
    db_path: DB = None,
) -> None:
    """Correct a semantic ID into an authoritative explicit fact (requires opt-in)."""
    with command_errors(), memory_service(ctx, db_path, semantic=True) as service:
        _print_facts([service.correct_semantic(identifier, key, value, category.value, _expiry(expires))])


@contextmanager
def github_errors() -> Iterator[None]:
    """Expose GitHub API and transport failures as nonzero, actionable command errors."""
    from github import GithubException  # noqa: PLC0415
    from requests.exceptions import RequestException  # noqa: PLC0415
    from urllib3.exceptions import HTTPError  # noqa: PLC0415

    try:
        yield
    except (GithubException, RequestException, HTTPError) as exc:
        console.print(f"GitHub error: {exc}", style="red", markup=False)
        raise typer.Exit(1) from exc


def _sync_summary(result: "SyncResult") -> None:
    console.print(
        f"Imported: {result.imported}; updated: {result.updated}; "
        f"pushed: {result.pushed}; unchanged: {result.unchanged}"
    )
    for task_id in result.task_ids:
        console.print(f"Task: {task_id}")
    for conflict in result.conflicts:
        console.print(f"Conflict: {conflict}", style="yellow", markup=False)
    if result.conflicts:
        raise typer.Exit(1)


@github.command(name="import")
def import_issues(
    ctx: typer.Context,
    repos: Annotated[list[str] | None, typer.Argument(help="owner/repo (defaults to configured repositories)")] = None,
    state: IssueState = IssueState.OPEN,
    db_path: DB = None,
) -> None:
    """Import issues into durable mapped tasks; repeated imports do not duplicate tasks."""
    from .agents.github_issues import GitHubIssueSyncService  # noqa: PLC0415

    with command_errors(), github_errors():
        names = repos or get_config().github_repos
        if not names:
            raise ValueError("Specify owner/repo or configure github_repos")
        with GitHubIssueSyncService(resolve_db(ctx, db_path)) as service:
            _sync_summary(service.import_issues(names, state=state.value))


@github.command(name="sync")
def sync_issues(
    ctx: typer.Context,
    repos: Annotated[list[str] | None, typer.Argument(help="Filter mapped owner/repo repositories")] = None,
    push: bool = False,
    db_path: DB = None,
) -> None:
    """Pull mapped issues; remote writes occur only with explicit --push."""
    from .agents.github_issues import GitHubIssueSyncService  # noqa: PLC0415

    with command_errors(), github_errors(), GitHubIssueSyncService(resolve_db(ctx, db_path)) as service:
        _sync_summary(service.sync(repos, push=push))
