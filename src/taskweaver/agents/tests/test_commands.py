"""Slash commands exercise local persistence and real preprocessing boundaries."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from github import Github

from taskweaver.agents.commands import CommandError, parse_command, process_command
from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.github_issues import GitHubIssueSyncService
from taskweaver.agents.memory import MemoryService
from taskweaver.config import Config
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.models import TaskCreate
from taskweaver.database.planning import PlanningService
from taskweaver.database.repository import TaskRepository


@pytest.fixture
def dependencies(tmp_path: Path) -> TaskDependencies:
    path = tmp_path / "commands.db"
    return TaskDependencies(
        TaskRepository(path),
        TaskDependencyRepository(path),
        CompletionRepository(path),
        "",
        user_id="alice",
        planning=PlanningService(path),
        memory=MemoryService(path, "alice"),
    )


def execute(text: str, dependencies: TaskDependencies, config: Config | None = None):
    command = parse_command(text)
    assert command is not None
    return process_command(command, dependencies, config or Config())


@pytest.mark.parametrize("text", ["/unknown", "/", "/plan", "/breakdown", "/review", "/review invalid", "/focus extra"])
def test_invalid_slash_is_local(text: str) -> None:
    with pytest.raises(CommandError):
        parse_command(text)
    assert parse_command("a normal conversation") is None


def test_per_command_help_and_missing_task_do_not_require_a_provider(dependencies: TaskDependencies) -> None:
    assert "/review TASK_UUID" in execute("/review --help", dependencies).message
    assert "UUID" in execute("/help /review", dependencies).message
    assert "learning gaps" in execute("/focus -h", dependencies).message
    with pytest.raises(CommandError, match="Task not found"):
        execute(f"/review {uuid4()}", dependencies)
    with pytest.raises(CommandError, match="Unknown command"):
        execute("/help imaginary", dependencies)


def test_review_uses_current_task_edges_exact_score_and_skill_evidence(dependencies: TaskDependencies) -> None:
    repo = dependencies.task_repo
    blocker = repo.create_task(TaskCreate(title="Learn basics", duration_min=20, llm_value=30, requirement="Read"))
    task = repo.create_task(
        TaskCreate(
            title="Implement parser",
            duration_min=45,
            llm_value=80,
            requirement="Works",
            skill_domain="python",
            required_skill_level=4,
            urgency=5,
        )
    )
    downstream = repo.create_task(TaskCreate(title="Release", duration_min=10, llm_value=90, requirement="Ship"))
    dependencies.dep_repo.add_dependency(task.task_id, blocker.task_id)
    dependencies.dep_repo.add_dependency(downstream.task_id, task.task_id)
    assert dependencies.planning is not None
    dependencies.planning.set_skill("python", 2, "Built a small command")

    result = execute(f"/review {task.task_id}", dependencies)
    assert result.mode == "review"
    context = json.loads(result.prompt.split("\n", 1)[1])
    assert context["task"]["task_id"] == str(task.task_id)
    assert context["task"]["status"] == "pending"
    assert [entry["task_id"] for entry in context["blockers"]] == [str(blocker.task_id)]
    assert [entry["task_id"] for entry in context["blocks"]] == [str(downstream.task_id)]
    assert context["skills"]["known_level"] == 2
    assert context["skills"]["blocked"]
    assert context["skills"]["learning_gap"]


def test_focus_separates_actionable_work_blockers_and_learning_gaps(dependencies: TaskDependencies) -> None:
    repo = dependencies.task_repo
    ready = repo.create_task(TaskCreate(title="Ready now", duration_min=10, llm_value=60, requirement="Do it"))
    blocked = repo.create_task(TaskCreate(title="Blocked work", duration_min=15, llm_value=90, requirement="Wait"))
    learning = repo.create_task(
        TaskCreate(
            title="Learning work",
            duration_min=20,
            llm_value=80,
            requirement="Practice",
            skill_domain="rust",
            required_skill_level=3,
        )
    )
    dependencies.dep_repo.add_dependency(blocked.task_id, ready.task_id)
    message = execute("/focus", dependencies).message
    ready_section, gaps_section = message.split("Learning gaps:")
    assert str(ready.task_id) in ready_section
    assert str(blocked.task_id) not in ready_section
    assert str(learning.task_id) not in ready_section
    assert str(learning.task_id) in gaps_section


def test_explicit_facts_are_user_scoped_correctable_expiring_and_deletable(dependencies: TaskDependencies) -> None:
    execute('/remember --category context "editor=vim"', dependencies)
    assert "editor = vim" in execute("/memories context", dependencies).message
    execute("/remember editor=helix", dependencies)
    assert "editor = helix" in execute("/memories", dependencies).message
    assert "vim" not in execute("/memories", dependencies).message
    assert not MemoryService(dependencies.task_repo.db_path, "bob").list_facts()
    expiry = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    execute(f"/remember --expires {expiry} expired=not visible", dependencies)
    assert "expired" not in execute("/memories", dependencies).message
    execute("/forget editor", dependencies)
    assert execute("/memories", dependencies).message == "No current memories."


@pytest.mark.parametrize(
    "text",
    [
        "/remember no-equals",
        "/remember --category unsupported key=value",
        "/remember --expires 2030-01-01 key=value",
        "/remember --expires bad key=value",
        "/remember --unknown value key=value",
        '/remember "unclosed',
        "/memories unsupported",
    ],
)
def test_invalid_fact_operations_do_not_write(text: str, dependencies: TaskDependencies) -> None:
    with pytest.raises(CommandError):
        execute(text, dependencies)
    assert dependencies.memory is not None
    assert not dependencies.memory.list_facts()


def test_github_without_repositories_is_actionable_and_local(dependencies: TaskDependencies) -> None:
    with pytest.raises(CommandError, match="No GitHub repositories"):
        execute("/github", dependencies)
    with pytest.raises(CommandError, match="OWNER/REPO"):
        parse_command("/github missing-owner")


def test_github_command_persists_real_import_without_model_or_push(dependencies, monkeypatch) -> None:
    issue = SimpleNamespace(
        number=7,
        title="Fix startup",
        body="Start without credentials",
        state="open",
        html_url="https://github.com/example/project/issues/7",
        pull_request=None,
        state_reason=None,
        updated_at=datetime.now(UTC),
    )
    repository = SimpleNamespace(full_name="example/project", get_issues=lambda **_kwargs: [issue])
    client = SimpleNamespace(get_repo=lambda _name: repository)
    service = GitHubIssueSyncService(dependencies.task_repo.db_path, client=cast("Github", client))
    monkeypatch.setattr("taskweaver.agents.github_issues.GitHubIssueSyncService", lambda _path: service)
    first = execute("/github example/project", dependencies).message
    second = execute("/github example/project", dependencies).message
    assert "1 imported" in first
    assert "0 imported" in second
    assert "No changes pushed" in first
    tasks = dependencies.task_repo.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].title == "Fix startup"


def test_quoted_fact_key_can_be_forgotten(dependencies: TaskDependencies) -> None:
    execute('/remember "work style=Morning focus"', dependencies)
    execute('/forget "work style"', dependencies)
    assert dependencies.memory is not None
    assert dependencies.memory.list_facts() == []


@pytest.mark.parametrize(
    "text", ['/forget ""', '/forget "unclosed', '/github "owner/repo', '/help "help', '/github ""']
)
def test_malformed_structured_arguments_are_local_errors(text: str) -> None:
    with pytest.raises(CommandError):
        parse_command(text)


def test_quoted_review_uuid_is_accepted(dependencies: TaskDependencies) -> None:
    task = dependencies.task_repo.create_task(
        TaskCreate(title="Review", duration_min=10, llm_value=50, requirement="Do")
    )
    assert execute(f'/review "{task.task_id}"', dependencies).mode == "review"


def test_unrepresentable_expiry_does_not_replace_fact(dependencies: TaskDependencies) -> None:
    execute("/remember drink=tea", dependencies)
    with pytest.raises(CommandError):
        execute("/remember --expires 0001-01-01T00:00:00+01:00 drink=coffee", dependencies)
    assert dependencies.memory is not None
    assert dependencies.memory.list_facts()[0].value == "tea"
