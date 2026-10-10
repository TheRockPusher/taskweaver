"""Real SQLite and PyGithub API-boundary coverage for durable issue lifecycles."""

import json
import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest
from github import Github, GithubException
from pydantic_ai import RunContext

from taskweaver.agents import research
from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.github_issues import GitHubIssueSyncService
from taskweaver.agents.memory import MemoryService
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import get_connection, init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.models import Task, TaskCreate, TaskStatus, TaskUpdate
from taskweaver.database.planning import PlanningService
from taskweaver.database.repository import TaskRepository
from taskweaver.database.schema import SCHEMA_VERSION


class GitHubAPI:
    """Replace only PyGithub's HTTP boundary, retaining real repository/issue parsing."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.client = Github(lazy=True)
        self.issues: dict[int, dict[str, Any]] = {}
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.failure: tuple[str, GithubException] | None = None
        requester = self.client.get_repo("owner/repo", lazy=True).requester
        monkeypatch.setattr(requester, "requestJsonAndCheck", self.request)

    def add(self, number: int, **fields: Any) -> None:
        self.issues[number] = {
            "id": 1000 + number,
            "number": number,
            "url": f"https://api.github.com/repos/owner/repo/issues/{number}",
            "html_url": f"https://github.com/owner/repo/issues/{number}",
            "title": f"Issue {number}",
            "body": "Original body",
            "state": "open",
            "state_reason": None,
            "updated_at": "2026-01-01T12:00:00Z",
        } | fields

    # PyGithub's requester invokes this callback with the public keyword `input`.
    def request(self, method: str, url: str, parameters=None, input=None, **_kwargs) -> tuple[dict[str, str], Any]:  # noqa: A002
        self.calls.append((method, url, input))
        if self.failure is not None and self.failure[0] == method:
            raise self.failure[1]
        if url.endswith("/issues"):
            state = (parameters or {}).get("state", "open")
            return {}, [dict(issue) for issue in self.issues.values() if state == "all" or issue["state"] == state]
        if "/issues/" in url:
            number = int(url.rsplit("/", 1)[1])
            if number not in self.issues:
                raise GithubException(404, {"message": "Not Found"})
            if method == "PATCH":
                self.issues[number].update(input)
                self.issues[number]["updated_at"] = "2026-01-02T12:00:00Z"
            return {}, dict(self.issues[number])
        return {}, {"full_name": "owner/repo", "url": "https://api.github.com/repos/owner/repo"}

    @property
    def writes(self) -> list[dict[str, Any]]:
        return [payload for method, _url, payload in self.calls if method == "PATCH" and payload is not None]


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Generator[GitHubAPI]:
    api_boundary = GitHubAPI(monkeypatch)
    try:
        yield api_boundary
    finally:
        api_boundary.client.close()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "tasks.db"


def stored(db_path: Path, task_id: UUID) -> Task:
    task = TaskRepository(db_path).get_task(task_id)
    assert task is not None
    return task


def test_repeated_import_is_durable_idempotent_and_excludes_pull_requests(db_path: Path, api: GitHubAPI) -> None:
    api.add(1)
    api.add(2, pull_request={"url": "https://api.github.com/repos/owner/repo/pulls/2"})
    first = GitHubIssueSyncService(db_path, client=api.client).import_issues(["OWNER/Repo", "owner/repo"])
    second = GitHubIssueSyncService(db_path, client=api.client).import_issues(["owner/repo"])
    assert first.imported == 1
    assert second.imported == 0
    assert second.unchanged == 1
    assert first.task_ids == second.task_ids
    assert len(TaskRepository(db_path).list_tasks()) == 1
    with get_connection(db_path) as conn:
        mapping = conn.execute("SELECT * FROM github_issue_mappings").fetchone()
        assert mapping["repo"] == "owner/repo"
        assert mapping["issue_number"] == 1
        assert mapping["task_id"] == str(first.task_ids[0])
        assert mapping["url"] == "https://github.com/owner/repo/issues/1"
        assert json.loads(mapping["remote_state"])["title"] == "Issue 1"
        assert json.loads(mapping["local_state"])["status"] == "pending"
    assert api.writes == []


def test_pull_updates_owned_fields_but_preserves_local_planning(db_path: Path, api: GitHubAPI) -> None:
    api.add(1)
    service = GitHubIssueSyncService(db_path, client=api.client)
    task_id = service.import_issues(["owner/repo"]).task_ids[0]
    planning = PlanningService(db_path)
    goal = planning.create_goal("Ship release")
    repo = TaskRepository(db_path)
    local = repo.update_task(
        task_id,
        TaskUpdate(
            duration_min=90,
            llm_value=84,
            urgency=5,
            importance=4,
            effort=2,
            goal_id=goal.goal_id,
            skill_domain="python",
            required_skill_level=4,
            requirement="Release includes regression coverage",
            category="release",
        ),
    )
    api.issues[1].update(title="Remote renamed", body=None)
    result = service.sync()
    updated = stored(db_path, task_id)
    assert result.updated == 1
    assert result.conflicts == []
    assert updated.title == "Remote renamed"
    assert updated.description is None
    for field in (
        "duration_min",
        "raw_duration_min",
        "llm_value",
        "urgency",
        "importance",
        "effort",
        "goal_id",
        "skill_domain",
        "required_skill_level",
        "requirement",
        "category",
        "priority_score",
    ):
        assert getattr(updated, field) == getattr(local, field)
    assert api.writes == []


@pytest.mark.parametrize(
    ("reason", "status"), [("completed", TaskStatus.COMPLETED), ("not_planned", TaskStatus.CANCELLED)]
)
def test_remote_close_and_reopen_never_fabricate_actual_time(
    db_path: Path, api: GitHubAPI, reason: str, status: TaskStatus
) -> None:
    api.add(1)
    service = GitHubIssueSyncService(db_path, client=api.client)
    task_id = service.import_issues(["owner/repo"]).task_ids[0]
    downstream = TaskRepository(db_path).create_task(
        TaskCreate(title="Dependent", duration_min=10, llm_value=50, requirement="Done")
    )
    dep_repo = TaskDependencyRepository(db_path)
    dep_repo.add_dependency(downstream.task_id, task_id)
    api.issues[1].update(state="closed", state_reason=reason)
    assert service.sync().updated == 1
    assert stored(db_path, task_id).status is status
    assert dep_repo.get_blockers(downstream.task_id) == []
    assert CompletionRepository(db_path).get_completion_by_task_id(task_id) is None
    api.issues[1].update(state="open", state_reason="reopened")
    assert service.sync().updated == 1
    assert stored(db_path, task_id).status is TaskStatus.PENDING
    assert dep_repo.get_blockers(downstream.task_id) == []
    assert CompletionRepository(db_path).get_completion_by_task_id(task_id) is None
    assert api.writes == []


def test_closed_import_uses_remote_reason_and_does_not_create_completion(db_path: Path, api: GitHubAPI) -> None:
    api.add(1, state="closed", state_reason="not_planned")
    result = GitHubIssueSyncService(db_path, client=api.client).import_issues(["owner/repo"], state="all")
    assert stored(db_path, result.task_ids[0]).status is TaskStatus.CANCELLED
    assert CompletionRepository(db_path).list_completions() == []


@pytest.mark.parametrize(
    ("status", "reason"), [(TaskStatus.COMPLETED, "completed"), (TaskStatus.CANCELLED, "not_planned")]
)
def test_status_push_requires_explicit_authorization_and_preserves_remote_content(
    db_path: Path, api: GitHubAPI, status: TaskStatus, reason: str
) -> None:
    api.add(1)
    service = GitHubIssueSyncService(db_path, client=api.client)
    task_id = service.import_issues(["owner/repo"]).task_ids[0]
    TaskRepository(db_path).update_task(task_id, TaskUpdate(status=status, title="Local title"))
    pull = service.sync()
    assert pull.pushed == 0
    assert stored(db_path, task_id).status is status
    assert api.writes == []
    push = service.sync(push=True)
    assert push.pushed == 1
    assert push.conflicts == []
    assert api.writes == [{"state": "closed", "state_reason": reason}]
    assert api.issues[1]["title"] == "Issue 1"
    assert service.sync(push=True).pushed == 0
    TaskRepository(db_path).update_task(task_id, TaskUpdate(status=TaskStatus.PENDING))
    assert service.sync(push=True).pushed == 1
    assert api.writes[-1] == {"state": "open", "state_reason": "reopened"}


def test_in_progress_is_local_metadata_not_a_remote_status_write(db_path: Path, api: GitHubAPI) -> None:
    api.add(1)
    service = GitHubIssueSyncService(db_path, client=api.client)
    task_id = service.import_issues(["owner/repo"]).task_ids[0]
    TaskRepository(db_path).mark_in_progress(task_id)
    assert service.sync(push=True).pushed == 0
    assert stored(db_path, task_id).status is TaskStatus.IN_PROGRESS
    assert api.writes == []
    api.issues[1].update(state="closed", state_reason="completed")
    assert service.sync().updated == 1
    assert stored(db_path, task_id).status is TaskStatus.COMPLETED


def test_both_changed_conflicts_persist_and_nonconflicting_fields_still_pull(db_path: Path, api: GitHubAPI) -> None:
    api.add(1)
    service = GitHubIssueSyncService(db_path, client=api.client)
    task_id = service.import_issues(["owner/repo"]).task_ids[0]
    repo = TaskRepository(db_path)
    repo.update_task(task_id, TaskUpdate(title="Local choice", status=TaskStatus.CANCELLED))
    api.issues[1].update(title="Remote choice", body="Remote body", state="closed", state_reason="completed")
    result = service.sync(push=True)
    assert len(result.conflicts) == 2
    assert result.updated == 1
    assert result.pushed == 0
    local = stored(db_path, task_id)
    assert local.title == "Local choice"
    assert local.status is TaskStatus.CANCELLED
    assert local.description == "Remote body"
    assert api.writes == []
    assert len(service.sync(push=True).conflicts) == 2
    repo.update_task(task_id, TaskUpdate(title="Remote choice", status=TaskStatus.COMPLETED))
    assert service.sync(push=True).conflicts == []
    assert service.sync().unchanged == 1


def test_local_only_edit_is_not_forgotten_before_later_remote_conflict(db_path: Path, api: GitHubAPI) -> None:
    api.add(1)
    service = GitHubIssueSyncService(db_path, client=api.client)
    task_id = service.import_issues(["owner/repo"]).task_ids[0]
    TaskRepository(db_path).update_task(task_id, TaskUpdate(description="Local body"))
    assert service.sync().conflicts == []
    api.issues[1]["body"] = "Later remote body"
    assert len(service.sync().conflicts) == 1
    assert stored(db_path, task_id).description == "Local body"


@pytest.mark.parametrize(("method", "status"), [("GET", 403), ("GET", 404), ("PATCH", 401), ("PATCH", 422)])
def test_api_errors_remain_visible_and_do_not_acknowledge_failed_push(
    db_path: Path, api: GitHubAPI, method: str, status: int
) -> None:
    api.add(1)
    service = GitHubIssueSyncService(db_path, client=api.client)
    task_id = service.import_issues(["owner/repo"]).task_ids[0]
    TaskRepository(db_path).mark_completed(task_id)
    with get_connection(db_path) as conn:
        before = tuple(
            conn.execute("SELECT remote_state, local_state, updated_at FROM github_issue_mappings").fetchone()
        )
    error = GithubException(status, {"message": "API denied request"})
    api.failure = method, error
    with pytest.raises(GithubException) as raised:
        service.sync(push=True)
    assert raised.value is error
    with get_connection(db_path) as conn:
        after = tuple(
            conn.execute("SELECT remote_state, local_state, updated_at FROM github_issue_mappings").fetchone()
        )
        assert after == before
    api.failure = None
    assert service.sync(push=True).pushed == 1


def test_task_and_mapping_insert_roll_back_atomically(db_path: Path, api: GitHubAPI) -> None:
    api.add(1)
    init_database(db_path)
    with get_connection(db_path) as conn, conn:
        conn.execute("""CREATE TRIGGER reject_mapping BEFORE INSERT ON github_issue_mappings
                     BEGIN SELECT RAISE(ABORT, 'mapping refused'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="mapping refused"):
        GitHubIssueSyncService(db_path, client=api.client).import_issues(["owner/repo"])
    assert TaskRepository(db_path).list_tasks() == []
    with get_connection(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM priority_history").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM github_issue_mappings").fetchone()[0] == 0


def test_version_five_migration_preserves_foreign_keys_and_all_product_history(db_path: Path) -> None:
    init_database(db_path)
    repo = TaskRepository(db_path)
    planning = PlanningService(db_path)
    goal = planning.create_goal("Preserve release")
    task = repo.create_task(
        TaskCreate(title="History", duration_min=30, llm_value=75, requirement="Done", goal_id=goal.goal_id)
    )
    completion = planning.complete_task(task.task_id, 45, "Evidence")
    MemoryService(db_path).remember("release", "Keep this", category="goal")
    planning.set_skill("python", 4, "Shipped software")
    tables = ("tasks", "goals", "completion", "priority_history", "memory_facts", "skill_assessments")
    with get_connection(db_path) as conn, conn:
        before = {
            table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]  # noqa: S608
            for table in tables
        }
        task_schema = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'tasks'").fetchone()[0]
        conn.execute("DROP TABLE github_issue_mappings")
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version VALUES (5, ?)", (datetime.now(UTC).isoformat(),))
    init_database(db_path)
    with get_connection(db_path) as conn:
        after = {
            table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]  # noqa: S608
            for table in tables
        }
        assert before == after
        assert conn.execute("SELECT sql FROM sqlite_master WHERE name = 'tasks'").fetchone()[0] == task_schema
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) FROM github_issue_mappings").fetchone()[0] == 0
    assert stored(db_path, task.task_id).goal_id == goal.goal_id
    assert CompletionRepository(db_path).get_completion(completion.completion_id) == completion


def test_research_import_persists_to_request_database_and_propagates_errors(
    db_path: Path, api: GitHubAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    api.add(1)
    monkeypatch.setattr(
        research, "GitHubIssueSyncService", lambda path: GitHubIssueSyncService(path, client=api.client)
    )
    deps = TaskDependencies(
        task_repo=TaskRepository(db_path),
        dep_repo=TaskDependencyRepository(db_path),
        completion_repo=CompletionRepository(db_path),
        memories="",
    )
    ctx = cast("RunContext[TaskDependencies]", SimpleNamespace(deps=deps))
    result = json.loads(research.github_import_tool(ctx, ["owner/repo"]))
    assert result["imported"] == 1
    assert stored(db_path, UUID(result["task_ids"][0])).title == "Issue 1"
    error = GithubException(403, {"message": "rate limited"})
    api.failure = "GET", error
    with pytest.raises(GithubException) as raised:
        research.github_import_tool(ctx, ["owner/repo"])
    assert raised.value is error


def test_repository_alias_selection_pulls_canonical_mapping(db_path: Path, api: GitHubAPI) -> None:
    api.add(1)
    service = GitHubIssueSyncService(db_path, client=api.client)
    task_id = service.import_issues(["old-owner/repo"]).task_ids[0]
    api.issues[1].update(state="closed", state_reason="completed")
    result = service.sync(["old-owner/repo"])
    assert result.updated == 1
    assert result.task_ids == [task_id]
    assert stored(db_path, task_id).status is TaskStatus.COMPLETED
    assert api.writes == []


def test_paginated_import_excludes_prs_on_every_page(
    db_path: Path, api: GitHubAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    api.add(1)
    api.add(2, pull_request={"url": "https://api.github.com/repos/owner/repo/pulls/2"})
    api.add(3)

    def paginated(method, url, parameters=None, input=None, **kwargs):  # noqa: A002
        parsed = urlsplit(url)
        if method == "GET" and parsed.path.endswith("/issues"):
            api.calls.append((method, url, input))
            if parse_qs(parsed.query).get("page") == ["2"]:
                return {}, [dict(api.issues[3])]
            return (
                {"link": '<https://api.github.com/repos/owner/repo/issues?page=2>; rel="next"'},
                [dict(api.issues[1]), dict(api.issues[2])],
            )
        return api.request(method, url, parameters=parameters, input=input, **kwargs)

    requester = api.client.get_repo("owner/repo", lazy=True).requester
    monkeypatch.setattr(requester, "requestJsonAndCheck", paginated)
    service = GitHubIssueSyncService(db_path, client=api.client)
    first = service.import_issues(["owner/repo"])
    repeated = service.import_issues(["owner/repo"])
    assert first.imported == 2
    assert repeated.imported == 0
    assert repeated.unchanged == 2
    assert set(first.task_ids) == set(repeated.task_ids)
    assert {task.title for task in TaskRepository(db_path).list_tasks()} == {"Issue 1", "Issue 3"}


def test_content_conflict_does_not_authorize_content_push_or_block_unconflicted_status(
    db_path: Path, api: GitHubAPI
) -> None:
    api.add(1)
    service = GitHubIssueSyncService(db_path, client=api.client)
    task_id = service.import_issues(["owner/repo"]).task_ids[0]
    TaskRepository(db_path).update_task(task_id, TaskUpdate(title="Local title", status=TaskStatus.COMPLETED))
    api.issues[1]["title"] = "Remote title"
    result = service.sync(push=True)
    assert result.pushed == 1
    assert len(result.conflicts) == 1
    assert stored(db_path, task_id).title == "Local title"
    assert api.issues[1]["title"] == "Remote title"
    assert api.writes == [{"state": "closed", "state_reason": "completed"}]
    repeated = service.sync(push=True)
    assert repeated.pushed == 0
    assert repeated.conflicts == result.conflicts
