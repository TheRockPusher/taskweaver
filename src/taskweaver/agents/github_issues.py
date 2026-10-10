"""Durable GitHub issue imports and conservative, explicitly authorized status sync."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Self
from uuid import UUID

from github import Auth, Github

from ..database.connection import get_connection
from ..database.models import Task, TaskCreate, TaskStatus, TaskUpdate
from ..database.repository import TaskRepository
from ..database.schema import SELECT_TASK_BY_ID

if TYPE_CHECKING:
    from github.Issue import Issue


@dataclass
class SyncResult:
    """Counts, affected task identities, and unresolved field conflicts for one request."""

    imported: int = 0
    updated: int = 0
    pushed: int = 0
    unchanged: int = 0
    conflicts: list[str] = field(default_factory=list)
    task_ids: list[UUID] = field(default_factory=list)


def _repos(repo_names: Sequence[str]) -> list[str]:
    result = []
    for repo_name in repo_names:
        name = repo_name.strip().casefold()
        owner, separator, repository = name.partition("/")
        if not separator or not owner or not repository or "/" in repository:
            msg = f"GitHub repository must be owner/repo: {name!r}"
            raise ValueError(msg)
        if name not in result:
            result.append(name)
    return result


def _remote_state(issue: Issue) -> dict[str, str | None]:
    if issue.state == "open":
        status = TaskStatus.PENDING
    elif issue.state == "closed":
        status = TaskStatus.CANCELLED if issue.state_reason == "not_planned" else TaskStatus.COMPLETED
    else:
        msg = f"Unsupported GitHub issue state: {issue.state!r}"
        raise ValueError(msg)
    return {
        "title": issue.title,
        "description": issue.body,
        "status": status.value,
        "github_state": issue.state,
        "state_reason": issue.state_reason,
        "updated_at": issue.updated_at.isoformat() if issue.updated_at is not None else None,
    }


def _local_state(task: Task) -> dict[str, str | None]:
    return {"title": task.title, "description": task.description, "status": task.status.value}


def _comparable(field_name: str, value: str | None) -> str | None:
    # GitHub has no in-progress state. Beginning work locally does not close/reopen an issue.
    return TaskStatus.PENDING.value if field_name == "status" and value == TaskStatus.IN_PROGRESS.value else value


class GitHubIssueSyncService:
    """Persist one local task per issue; never write GitHub without an explicit push flag.

    Imported tasks receive neutral working estimates (30 minutes, value 50), not
    fabricated completion times. Subsequent pulls own only title, description and
    status; all local planning fields remain authoritative. Divergent edits retain
    their previous common ancestor until the user resolves the conflicted field.
    API errors propagate rather than masquerading as an empty import.
    """

    def __init__(self, db_path: Path, client: Github | None = None, token: str | None = None) -> None:
        self.db_path = db_path
        self.task_repo = TaskRepository(db_path)
        self._owns_client = client is None
        if client is None:
            token = token if token is not None else os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
            client = Github(auth=Auth.Token(token) if token and token.strip() else None, retry=None, timeout=15)
        self.client = client

    def __enter__(self) -> Self:
        """Return this service for scoped client ownership."""
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        """Release an internally owned client when the scope ends."""
        self.close()

    def close(self) -> None:
        """Close the internally created HTTP client; injected clients remain caller-owned."""
        if self._owns_client:
            self.client.close()
            self._owns_client = False

    def import_issues(self, repo_names: Sequence[str], *, state: str = "open") -> SyncResult:
        """Import open (default), closed, or all issues, excluding pull requests.

        Repeated imports reconcile existing mappings instead of creating duplicates.
        A task and its initial mapping are committed or rolled back together.
        """
        if state not in {"open", "closed", "all"}:
            msg = "GitHub import state must be open, closed, or all"
            raise ValueError(msg)
        result = SyncResult()
        for name in _repos(repo_names):
            repo = self.client.get_repo(name)
            canonical = repo.full_name.casefold()
            for issue in repo.get_issues(state=state):
                if issue.pull_request is None:
                    self._reconcile(canonical, issue, result, push=False)
        return result

    def sync(self, repo_names: Sequence[str] | None = None, *, push: bool = False) -> SyncResult:
        """Pull mapped issues, optionally pushing only unconflicted local status edits.

        None selects every mapped repository; an empty sequence selects none. Missing
        or inaccessible remote issues raise the original GitHub API error.
        """
        names = None if repo_names is None else _repos(repo_names)
        with get_connection(self.db_path) as conn:
            mappings = conn.execute(
                "SELECT repo, issue_number FROM github_issue_mappings ORDER BY repo, issue_number"
            ).fetchall()
        result = SyncResult()
        repositories = {}
        for mapping in mappings:
            name = mapping["repo"]
            if names is not None and name not in names:
                continue
            if name not in repositories:
                repositories[name] = self.client.get_repo(name)
            issue = repositories[name].get_issue(mapping["issue_number"])
            if issue.pull_request is not None:
                msg = f"Mapped GitHub issue is now a pull request: {name}#{issue.number}"
                raise ValueError(msg)
            self._reconcile(name, issue, result, push=push)
        return result

    @staticmethod
    def _push_status(issue: Issue, local_value: str | None, remote: dict[str, str | None]) -> None:
        """Push only the authorized status and refresh its remote snapshot."""
        state = "open" if local_value == TaskStatus.PENDING.value else "closed"
        if state == "open":
            reason = "reopened"
        else:
            reason = "not_planned" if local_value == TaskStatus.CANCELLED.value else "completed"
        issue.edit(state=state, state_reason=reason)
        remote["status"] = local_value
        remote["github_state"] = state
        remote["state_reason"] = reason
        remote["updated_at"] = issue.updated_at.isoformat() if issue.updated_at is not None else None

    @staticmethod
    def _refresh_remote_metadata(baseline: dict[str, str | None], remote: dict[str, str | None]) -> None:
        """Advance status metadata only when the corresponding status is acknowledged."""
        baseline["updated_at"] = remote["updated_at"]
        if baseline["status"] == remote["status"]:
            baseline["github_state"] = remote["github_state"]
            baseline["state_reason"] = remote["state_reason"]

    def _reconcile(self, name: str, issue: Issue, result: SyncResult, *, push: bool) -> None:
        remote = _remote_state(issue)
        with get_connection(self.db_path) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            mapping = conn.execute(
                "SELECT * FROM github_issue_mappings WHERE repo = ? AND issue_number = ?", (name, issue.number)
            ).fetchone()
            if mapping is None:
                task = self.task_repo.create_task(
                    TaskCreate(
                        title=issue.title,
                        description=issue.body,
                        duration_min=30,
                        llm_value=50,
                        requirement=f"Resolve GitHub issue {name}#{issue.number}",
                        category="github",
                    ),
                    connection=conn,
                )
                if remote["status"] != TaskStatus.PENDING.value:
                    task = self.task_repo.update_task(
                        task.task_id, TaskUpdate(status=TaskStatus(str(remote["status"]))), connection=conn
                    )
                baseline_remote = remote
                baseline_local = _local_state(task)
                imported, updated, pushed = True, False, False
                conflicts = []
            else:
                task = Task.model_validate(dict(conn.execute(SELECT_TASK_BY_ID, (mapping["task_id"],)).fetchone()))
                local = _local_state(task)
                baseline_remote = json.loads(mapping["remote_state"])
                baseline_local = json.loads(mapping["local_state"])
                changes = {}
                conflicts = []
                pushed = False
                for field_name in ("title", "description", "status"):
                    remote_value = remote[field_name]
                    local_value = _comparable(field_name, local[field_name])
                    remote_changed = remote_value != baseline_remote[field_name]
                    local_changed = local_value != _comparable(field_name, baseline_local[field_name])
                    if remote_changed and local_changed and local_value != remote_value:
                        conflicts.append(f"{name}#{issue.number}: conflicting {field_name} edits (task {task.task_id})")
                        continue
                    if remote_changed and local_value != remote_value:
                        changes[field_name] = remote_value
                    elif field_name == "status" and local_changed and local_value != remote_value and push:
                        TaskUpdate.model_validate(changes)
                        self._push_status(issue, local_value, remote)
                        pushed = True
                    elif local_changed and local_value != remote_value:
                        # Local-only content edits are never pushed; status edits await explicit push.
                        continue
                    baseline_remote[field_name] = remote[field_name]
                    baseline_local[field_name] = changes.get(field_name, local[field_name])
                self._refresh_remote_metadata(baseline_remote, remote)
                imported, updated = False, bool(changes)
                if changes:
                    task = self.task_repo.update_task(task.task_id, TaskUpdate.model_validate(changes), connection=conn)
            conn.execute(
                """INSERT INTO github_issue_mappings
                (repo, issue_number, task_id, url, remote_state, local_state, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(repo, issue_number) DO UPDATE SET
                url = excluded.url, remote_state = excluded.remote_state,
                local_state = excluded.local_state, updated_at = excluded.updated_at""",
                (
                    name,
                    issue.number,
                    str(task.task_id),
                    issue.html_url,
                    json.dumps(baseline_remote),
                    json.dumps(baseline_local),
                    datetime.now(UTC).isoformat(),
                ),
            )
        result.task_ids.append(task.task_id)
        result.conflicts.extend(conflicts)
        result.imported += int(imported)
        result.updated += int(updated)
        result.pushed += int(pushed)
        result.unchanged += int(not (imported or updated or pushed or conflicts))
