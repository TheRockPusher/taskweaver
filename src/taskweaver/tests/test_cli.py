"""CLI boundary regressions exercising real local persistence and transitions."""

import re
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from github import GithubException
from rich.console import Console
from typer.testing import CliRunner

from taskweaver.agents.memory import MemoryService
from taskweaver.cli import app
from taskweaver.config import Config
from taskweaver.database import TaskRepository, init_database
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.models import CompletionStatus, TaskCreate, TaskStatus, TaskUpdate
from taskweaver.database.planning import PlanningService
from taskweaver.database.priority_service import PriorityService

runner = CliRunner(env={"NO_COLOR": "1"})


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    path = tmp_path / "tasks.db"
    init_database(path)
    return path


@pytest.fixture(autouse=True)
def offline_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskweaver.cli_integrations.get_config", lambda: Config(user_id="configured-user"))


@pytest.fixture
def sample_task(test_db: Path) -> str:
    task = TaskRepository(test_db).create_task(
        TaskCreate(
            title="Sample task",
            description="Sample description",
            duration_min=30,
            llm_value=50,
            requirement="Visible result",
        )
    )
    return str(task.task_id)


def invoke(db: Path, *args: str):
    return runner.invoke(app, ["--db", str(db), *args])


def create(db: Path, title: str, *args: str):
    return invoke(db, "create", title, "--duration", "30", "--value", "50", "--req", "Result", *args)


def test_create_full_metadata_and_validate_bounds(test_db: Path) -> None:
    goal = PlanningService(test_db).create_goal("Ship product")
    result = create(
        test_db,
        "Implement",
        "--desc",
        "Keep context",
        "--urgency",
        "5",
        "--importance",
        "4",
        "--effort",
        "2",
        "--category",
        "coding",
        "--goal",
        str(goal.goal_id),
        "--domain",
        "python",
        "--required-skill-level",
        "3",
    )
    assert result.exit_code == 0, result.output
    task = TaskRepository(test_db).list_tasks()[0]
    assert (task.urgency, task.importance, task.effort) == (5, 4, 2)
    assert (task.category, task.goal_id, task.skill_domain, task.required_skill_level) == (
        "coding",
        goal.goal_id,
        "python",
        3,
    )
    assert task.description == "Keep context"
    assert task.raw_duration_min == 30
    assert create(test_db, "Invalid", "--effort", "6").exit_code != 0
    assert len(TaskRepository(test_db).list_tasks()) == 1


def test_command_local_database_overrides_root(test_db: Path, tmp_path: Path) -> None:
    other = tmp_path / "other.db"
    result = create(test_db, "Elsewhere", "--db", str(other))
    assert result.exit_code == 0, result.output
    assert TaskRepository(test_db).list_tasks() == []
    assert TaskRepository(other).list_tasks()[0].title == "Elsewhere"


def test_runtime_default_database_is_resolved_per_invocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = [tmp_path / "first.db", tmp_path / "second.db"]
    for path in paths:
        monkeypatch.setattr("taskweaver.cli_planning.get_paths", lambda path=path: SimpleNamespace(database_file=path))
        result = runner.invoke(app, ["create", path.stem, "--duration", "10", "--value", "0", "--req", "Done"])
        assert result.exit_code == 0, result.output
    assert [TaskRepository(path).list_tasks()[0].title for path in paths] == ["first", "second"]


def test_edit_omitted_fields_preserve_metadata_and_raw_duration(test_db: Path) -> None:
    goal = PlanningService(test_db).create_goal("Goal")
    create(
        test_db,
        "Task",
        "--desc",
        "Context",
        "--goal",
        str(goal.goal_id),
        "--domain",
        "python",
        "--required-skill-level",
        "4",
    )
    task = TaskRepository(test_db).list_tasks()[0]
    result = invoke(test_db, "edit", str(task.task_id), "--title", "Renamed", "--duration", "60", "--value", "0")
    assert result.exit_code == 0, result.output
    task = TaskRepository(test_db).get_task(task.task_id)
    assert task is not None
    assert (task.title, task.duration_min, task.raw_duration_min, task.llm_value) == ("Renamed", 60, 30, 0)
    assert (task.description, task.goal_id, task.skill_domain, task.required_skill_level) == (
        "Context",
        goal.goal_id,
        "python",
        4,
    )
    assert (
        invoke(
            test_db,
            "edit",
            str(task.task_id),
            "--clear-description",
            "--clear-goal",
            "--clear-domain",
            "--clear-required-skill-level",
        ).exit_code
        == 0
    )
    task = TaskRepository(test_db).get_task(task.task_id)
    assert task is not None
    assert (task.description, task.goal_id, task.skill_domain, task.required_skill_level) == (None, None, None, None)


def test_edit_conflicting_clear_and_no_fields_leave_task_unchanged(test_db: Path, sample_task: str) -> None:
    assert invoke(test_db, "edit", sample_task).exit_code == 1
    result = invoke(test_db, "edit", sample_task, "--desc", "New", "--clear-description")
    assert result.exit_code == 1
    task = TaskRepository(test_db).get_task(UUID(sample_task))
    assert task is not None
    assert task.description == "Sample description"


def test_list_filters_status_and_cd3_is_distinct_from_mcda(test_db: Path) -> None:
    repo = TaskRepository(test_db)
    high_score = repo.create_task(
        TaskCreate(
            title="Strategic", duration_min=100, llm_value=1, requirement="Done", urgency=5, importance=5, effort=1
        )
    )
    high_cd3 = repo.create_task(
        TaskCreate(title="Quick", duration_min=1, llm_value=100, requirement="Done", urgency=1, importance=1, effort=5)
    )
    score = invoke(test_db, "ls", "--sort", "score", "--limit", "1")
    cd3 = invoke(test_db, "ls", "--sort", "cd3", "--limit", "1")
    assert score.exit_code == cd3.exit_code == 0
    assert "Strategic" in score.output
    assert "Quick" not in score.output
    assert "Quick" in cd3.output
    assert "Strategic" not in cd3.output
    repo.update_task(high_score.task_id, TaskUpdate(status=TaskStatus.IN_PROGRESS))
    result = invoke(test_db, "ls", "--status", "in_progress")
    assert result.exit_code == 0
    assert "Strategic" in result.output
    assert "Quick" not in result.output
    assert repo.get_task(high_cd3.task_id) is not None


def test_inherited_priority_ordering(test_db: Path) -> None:
    repo = TaskRepository(test_db)
    low = repo.create_task(
        TaskCreate(
            title="Prerequisite", duration_min=30, llm_value=5, requirement="Done", urgency=1, importance=1, effort=5
        )
    )
    high = repo.create_task(
        TaskCreate(title="Outcome", duration_min=30, llm_value=5, requirement="Done", urgency=5, importance=5, effort=1)
    )
    assert invoke(test_db, "createDep", str(high.task_id), str(low.task_id)).exit_code == 0
    result = invoke(test_db, "ls", "--sort", "priority")
    assert result.exit_code == 0, result.output
    assert result.output.index("Prerequisite") < result.output.index("Outcome")


@pytest.mark.parametrize("command", ["ls", "lso"])
def test_compact_list_preserves_readability(
    test_db: Path, sample_task: str, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr("taskweaver.cli.console", Console(width=80, color_system=None))
    TaskRepository(test_db).update_task(UUID(sample_task), TaskUpdate(status=TaskStatus.IN_PROGRESS))
    result = invoke(test_db, command)
    assert result.exit_code == 0, result.output
    assert "Sample task" in result.output
    assert "in progress" in result.output
    assert "30m" in result.output
    assert "Sample description" not in result.output
    assert all(len(line) <= 80 for line in result.output.splitlines())
    assert sample_task in result.output


def test_reading_priority_history_is_idempotent(test_db: Path, sample_task: str) -> None:
    assert invoke(test_db, "edit", sample_task, "--urgency", "5").exit_code == 0
    result = invoke(test_db, "show", sample_task, "--explain-priority")
    assert result.exit_code == 0, result.output
    events = PriorityService(test_db).history(UUID(sample_task))
    assert invoke(test_db, "score", sample_task).exit_code == 0
    assert PriorityService(test_db).history(UUID(sample_task)) == events


def test_focus_and_skill_matching_exclude_blocked_work_and_show_gaps(test_db: Path) -> None:
    repo = TaskRepository(test_db)
    ready = repo.create_task(TaskCreate(title="Ready", duration_min=30, llm_value=5, requirement="Done"))
    gap = repo.create_task(
        TaskCreate(
            title="Advanced",
            duration_min=30,
            llm_value=5,
            requirement="Done",
            skill_domain="python",
            required_skill_level=4,
        )
    )
    blocked = repo.create_task(TaskCreate(title="Blocked task", duration_min=30, llm_value=5, requirement="Done"))
    invoke(test_db, "createDep", str(blocked.task_id), str(ready.task_id))
    result = invoke(test_db, "focus")
    assert result.exit_code == 0, result.output
    assert "Ready" in result.output
    assert "Advanced" in result.output
    assert "Blocked task" not in result.output
    result = invoke(test_db, "ls", "--match-skills")
    assert "Ready" in result.output
    assert "Advanced" not in result.output
    assert "Blocked task" not in result.output
    assert invoke(test_db, "skills", "set", "python", "4", "--evidence", "Reviewed project").exit_code == 0
    result = invoke(test_db, "ls", "--match-skills")
    assert "Advanced" in result.output
    assert PlanningService(test_db).match(gap.task_id).ready


def test_completion_records_actuals_releases_blockers_and_goal_progress(test_db: Path) -> None:
    goal = PlanningService(test_db).create_goal("Goal")
    create(test_db, "First", "--goal", str(goal.goal_id), "--category", "coding")
    first = TaskRepository(test_db).list_tasks()[0]
    create(test_db, "Next", "--goal", str(goal.goal_id))
    next_task = TaskRepository(test_db).list_tasks()[0]
    invoke(test_db, "createDep", str(next_task.task_id), str(first.task_id))
    result = invoke(test_db, "complete", str(first.task_id), "--actual", "45", "--conclusion", "Delivered")
    assert result.exit_code == 0, result.output
    completion = CompletionRepository(test_db).get_completion_by_task_id(first.task_id)
    assert completion is not None
    assert (completion.duration_actual, completion.conclusion, completion.category) == (45, "Delivered", "coding")
    assert TaskDependencyRepository(test_db).get_blockers(next_task.task_id) == []
    progress = invoke(test_db, "goals", "progress", str(goal.goal_id))
    assert progress.exit_code == 0
    assert "1/2" in progress.output
    assert invoke(test_db, "complete", str(first.task_id), "--actual", "45", "--conclusion", "Delivered").exit_code == 0
    assert invoke(test_db, "complete", str(first.task_id), "--actual", "44").exit_code == 1
    assert CompletionRepository(test_db).get_completion_by_task_id(first.task_id) == completion


def test_cancel_unknown_actual_does_not_invent_learning_evidence(test_db: Path, sample_task: str) -> None:
    result = invoke(test_db, "cancel", sample_task)
    assert result.exit_code == 0, result.output
    task = TaskRepository(test_db).get_task(UUID(sample_task))
    assert task is not None
    assert task.status == TaskStatus.CANCELLED
    assert CompletionRepository(test_db).get_completion_by_task_id(UUID(sample_task)) is None
    assert PlanningService(test_db).insights() == []


def test_cancel_with_actual_records_cancellation(test_db: Path, sample_task: str) -> None:
    result = invoke(test_db, "cancel", sample_task, "--actual", "5", "--conclusion", "Stopped")
    assert result.exit_code == 0, result.output
    completion = CompletionRepository(test_db).get_completion_by_task_id(UUID(sample_task))
    assert completion is not None
    assert completion.status == CompletionStatus.CANCELLED
    assert completion.duration_actual == 5
    assert completion.conclusion == "Stopped"


def test_goals_edit_link_delete_preserve_task(test_db: Path, sample_task: str) -> None:
    assert invoke(test_db, "goals", "create", "Outcome", "--description", "Keep this").exit_code == 0
    goal = PlanningService(test_db).list_goals()[0]
    assert invoke(test_db, "goals", "edit", str(goal.goal_id), "--title", "New outcome").exit_code == 0
    updated = PlanningService(test_db).get_goal(goal.goal_id)
    assert updated is not None
    assert updated.description == "Keep this"
    assert invoke(test_db, "goals", "link", sample_task, "--goal-id", str(goal.goal_id)).exit_code == 0
    assert invoke(test_db, "goals", "list").exit_code == 0
    assert "0/1" in invoke(test_db, "goals", "show", str(goal.goal_id)).output
    assert invoke(test_db, "goals", "link", sample_task, "--clear").exit_code == 0
    assert invoke(test_db, "goals", "delete", str(goal.goal_id)).exit_code == 0
    task = TaskRepository(test_db).get_task(UUID(sample_task))
    assert task is not None
    assert task.goal_id is None


def test_skill_history_retains_evidence(test_db: Path) -> None:
    for level, evidence in ((2, "Tutorial"), (4, "Independent delivery")):
        assert invoke(test_db, "skills", "set", "python", str(level), "--evidence", evidence).exit_code == 0
    result = invoke(test_db, "skills", "history", "python")
    assert result.exit_code == 0, result.output
    assert "Tutorial" in result.output
    assert "Independent delivery" in result.output
    assert len(PlanningService(test_db).skill_history("python")) == 2
    assert "Independent delivery" in invoke(test_db, "skills", "list").output


def test_insights_automatic_adjustment_requires_real_samples(test_db: Path) -> None:
    for index in range(3):
        create(test_db, f"Observed {index}", "--category", "coding")
        task = TaskRepository(test_db).list_tasks()[0]
        assert invoke(test_db, "complete", str(task.task_id), "--actual", "60").exit_code == 0
    result = invoke(test_db, "insights", "--category", "coding", "--baseline", "30")
    assert result.exit_code == 0, result.output
    estimate = PlanningService(test_db).estimate("coding", 30)
    assert estimate.adjusted_minutes == 60
    assert estimate.sample_count == 3
    assert "60m" in result.output
    assert "yes" in result.output
    assert "True" not in result.output
    assert create(test_db, "Adjusted", "--category", "coding").exit_code == 0
    task = TaskRepository(test_db).list_tasks()[0]
    assert (task.duration_min, task.raw_duration_min) == (60, 30)


def test_weights_finite_sum_validation_and_persistence(test_db: Path) -> None:
    original = PriorityService(test_db).weights
    names = ("urgency", "importance", "effort", "dependencies", "age")
    for values in (("nan", "0.35", "0.15", "0.1", "0.1"), ("0.4", "0.4", "0.4", "0.4", "0.4")):
        args = [arg for name, value in zip(names, values, strict=True) for arg in (f"--{name}", value)]
        assert invoke(test_db, "weights", "set", *args).exit_code == 1
        assert PriorityService(test_db).weights == original
    assert (
        invoke(
            test_db,
            "weights",
            "set",
            "--urgency",
            "0.2",
            "--importance",
            "0.4",
            "--effort",
            "0.2",
            "--dependencies",
            "0.1",
            "--age",
            "0.1",
        ).exit_code
        == 0
    )
    assert PriorityService(test_db).weights.urgency == 0.2
    assert "0.2" in invoke(test_db, "weights", "show").output


def test_memory_identity_replacement_search_forget_and_expiry(test_db: Path) -> None:
    assert invoke(test_db, "memory", "remember", "hours", "Morning").exit_code == 0
    assert MemoryService(test_db, "configured-user").list_facts()[0].value == "Morning"
    assert invoke(test_db, "memory", "update", "hours", "Evening").exit_code == 0
    assert "Evening" in invoke(test_db, "memory", "search", "hours").output
    assert "Morning" not in invoke(test_db, "memory", "list").output
    assert invoke(test_db, "memory", "--user", "other", "remember", "hours", "Afternoon").exit_code == 0
    assert "Afternoon" not in invoke(test_db, "memory", "list").output
    assert invoke(test_db, "memory", "forget", "hours").exit_code == 0
    assert MemoryService(test_db, "configured-user").list_facts() == []
    assert (
        invoke(test_db, "memory", "remember", "stale", "Value", "--expires", "2000-01-01T00:00:00+00:00").exit_code == 0
    )
    assert invoke(test_db, "memory", "expire").exit_code == 0
    assert MemoryService(test_db, "configured-user").purge_expired() == 0
    assert MemoryService(test_db, "other").list_facts()[0].value == "Afternoon"


def test_memory_semantic_management_requires_opt_in(test_db: Path) -> None:
    result = invoke(test_db, "memory", "semantic-list")
    assert result.exit_code == 1
    assert "disabled" in result.output
    assert invoke(test_db, "memory", "remember", "bad", "Value", "--expires", "2030-01-01").exit_code == 1
    assert MemoryService(test_db, "configured-user").list_facts() == []


@pytest.mark.parametrize("command", ["show", "score", "complete", "cancel", "blocker", "edit"])
def test_missing_task_errors_are_nonzero(test_db: Path, command: str) -> None:
    args = [command, str(uuid4())]
    if command == "complete":
        args += ["--actual", "10"]
    if command == "edit":
        args += ["--title", "Missing"]
    result = invoke(test_db, *args)
    assert result.exit_code == 1, result.output
    assert "not found" in result.output.lower()
    assert result.stdout == ""
    assert "not found" in result.stderr.lower()
    assert "Traceback" not in result.stderr


def test_dependency_cycle_error_and_removal(test_db: Path) -> None:
    create(test_db, "First")
    create(test_db, "Second")
    first, second = TaskRepository(test_db).list_tasks()
    assert invoke(test_db, "createDep", str(first.task_id), str(second.task_id)).exit_code == 0
    assert invoke(test_db, "createDep", str(second.task_id), str(first.task_id)).exit_code == 1
    assert second.title in invoke(test_db, "blocker", str(first.task_id)).output
    assert invoke(test_db, "rmdep", str(first.task_id), str(second.task_id)).exit_code == 0
    assert TaskDependencyRepository(test_db).get_blockers(first.task_id) == []


def test_delete_confirmation_preserves_then_removes(test_db: Path, sample_task: str) -> None:
    result = runner.invoke(app, ["rm", sample_task, "--db", str(test_db)], input="n\n")
    assert result.exit_code != 0
    assert TaskRepository(test_db).get_task(UUID(sample_task)) is not None
    result = runner.invoke(app, ["rm", sample_task, "--db", str(test_db)], input="y\n")
    assert result.exit_code == 0
    assert TaskRepository(test_db).get_task(UUID(sample_task)) is None


def test_restart_preserves_and_requires_confirmation_to_delete(test_db: Path, sample_task: str) -> None:
    assert invoke(test_db, "restartDB").exit_code == 0
    assert TaskRepository(test_db).get_task(UUID(sample_task)) is not None
    result = runner.invoke(app, ["--db", str(test_db), "restartDB", "--delete"], input="n\n")
    assert result.exit_code != 0
    assert TaskRepository(test_db).get_task(UUID(sample_task)) is not None
    result = runner.invoke(app, ["--db", str(test_db), "restartDB", "--delete"], input="y\n")
    assert result.exit_code == 0, result.output
    assert TaskRepository(test_db).list_tasks() == []


def test_noninteractive_no_arguments_prints_help_and_version_is_metadata() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    assert "Usage" in result.output
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert version("taskweaver") in result.output


@pytest.fixture
def github_boundary(monkeypatch: pytest.MonkeyPatch):
    """Supply remote issue data at the GitHub client boundary; keep sync logic real."""
    issue = SimpleNamespace(
        number=7,
        title="Remote task",
        body="Remote context",
        state="open",
        state_reason=None,
        updated_at=None,
        pull_request=None,
        html_url="https://github.com/team/project/issues/7",
    )

    def edit(**changes):
        for field, value in changes.items():
            setattr(issue, field, value)

    issue.edit = edit
    repo = SimpleNamespace(
        full_name="team/project", get_issues=lambda **_kwargs: [issue], get_issue=lambda _number: issue
    )
    client = SimpleNamespace(get_repo=lambda _name: repo, close=lambda: None)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("taskweaver.agents.github_issues.Github", lambda **_kwargs: client)
    return issue


def test_github_import_dedup_pull_and_explicit_push(test_db: Path, github_boundary) -> None:
    for _ in range(2):
        result = invoke(test_db, "github", "import", "team/project")
        assert result.exit_code == 0, result.output
    tasks = TaskRepository(test_db).list_tasks()
    assert len(tasks) == 1
    task = tasks[0]
    github_boundary.title = "Remote update"
    result = invoke(test_db, "github", "sync")
    assert result.exit_code == 0, result.output
    updated = TaskRepository(test_db).get_task(task.task_id)
    assert updated is not None
    assert updated.title == "Remote update"
    assert invoke(test_db, "complete", str(task.task_id), "--actual", "20").exit_code == 0
    assert invoke(test_db, "github", "sync").exit_code == 0
    assert github_boundary.state == "open"
    assert invoke(test_db, "github", "sync", "--push").exit_code == 0
    assert (github_boundary.state, github_boundary.state_reason) == ("closed", "completed")


def test_github_conflict_does_not_overwrite_local_or_remote(test_db: Path, github_boundary) -> None:
    assert invoke(test_db, "github", "import", "team/project").exit_code == 0
    task = TaskRepository(test_db).list_tasks()[0]
    assert invoke(test_db, "edit", str(task.task_id), "--title", "Local change").exit_code == 0
    github_boundary.title = "Remote change"
    result = invoke(test_db, "github", "sync", "--push")
    assert result.exit_code == 1
    assert "Conflict" in result.output
    updated = TaskRepository(test_db).get_task(task.task_id)
    assert updated is not None
    assert updated.title == "Local change"
    assert github_boundary.title == "Remote change"


def test_github_remote_error_is_not_empty_success(test_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def get_repo(_name):
        raise GithubException(403, {"message": "rate limited"})

    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(
        "taskweaver.agents.github_issues.Github",
        lambda **_kwargs: SimpleNamespace(get_repo=get_repo, close=lambda: None),
    )
    result = invoke(test_db, "github", "import", "team/project")
    assert result.exit_code == 1
    assert "rate limited" in result.output
    assert TaskRepository(test_db).list_tasks() == []


def test_local_workflows_without_provider_credentials(test_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "TASKWEAVER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert create(test_db, "Offline task").exit_code == 0
    assert invoke(test_db, "ls").exit_code == 0
    assert invoke(test_db, "focus").exit_code == 0
    assert invoke(test_db, "goals", "create", "Offline goal").exit_code == 0
    assert invoke(test_db, "memory", "remember", "preference", "Quiet mornings").exit_code == 0
    assert TaskRepository(test_db).list_tasks()[0].title == "Offline task"
    assert MemoryService(test_db, "configured-user").list_facts()[0].value == "Quiet mornings"


def test_recalculate_is_idempotent_and_limit_zero_is_empty(test_db: Path, sample_task: str) -> None:
    before = PriorityService(test_db).history(UUID(sample_task))
    result = invoke(test_db, "recalc-priorities")
    assert result.exit_code == 0, result.output
    assert PriorityService(test_db).history(UUID(sample_task)) == before
    result = invoke(test_db, "ls", "--sort", "score", "--limit", "0")
    assert result.exit_code == 0
    assert "Sample task" not in result.output


def test_user_content_is_rendered_literally(test_db: Path) -> None:
    assert create(test_db, "[red]Literal[/red]").exit_code == 0
    assert "[red]Literal[/red]" in invoke(test_db, "ls").output
    assert invoke(test_db, "memory", "remember", "markup", "[bold]Fact[/bold]").exit_code == 0
    assert "[bold]Fact[/bold]" in invoke(test_db, "memory", "list").output


def test_goal_list_keeps_complete_identifiers_at_terminal_width(test_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskweaver.cli_planning.console", Console(width=80, color_system=None))
    goal = PlanningService(test_db).create_goal("Ship a useful tool")
    result = invoke(test_db, "goals", "list")
    assert result.exit_code == 0, result.output
    assert str(goal.goal_id) in result.output
    assert all(word in result.output for word in goal.title.split())


def test_score_components_remain_readable_at_terminal_width(
    test_db: Path, sample_task: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("taskweaver.cli_planning.console", Console(width=80, color_system=None))
    result = invoke(test_db, "score", sample_task)
    assert result.exit_code == 0, result.output
    assert "dependencies" in result.output
    assert "Contribution" in result.output
    assert "…" not in result.output
    assert not re.search(r"\d[eE][+-]\d+", result.output)
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", result.output)


def test_oversized_duration_is_a_clean_error_without_partial_task(test_db: Path) -> None:
    result = invoke(test_db, "create", "Too large", "--duration", str(2**80), "--value", "1", "--req", "Done")
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert TaskRepository(test_db).list_tasks() == []


def test_noninteractive_setup_reports_one_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskweaver.setup.sys.stdin.isatty", lambda: False)
    result = runner.invoke(app, ["setup"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert len(result.stderr.splitlines()) == 1


@pytest.mark.parametrize("width", [80, 120])
def test_task_details_are_human_readable_and_preserve_values(
    test_db: Path, sample_task: str, monkeypatch: pytest.MonkeyPatch, width: int
) -> None:
    monkeypatch.setattr("taskweaver.cli.console", Console(width=width, color_system=None))
    assert invoke(test_db, "edit", sample_task, "--duration", "60", "--clear-description").exit_code == 0
    result = invoke(test_db, "show", sample_task)
    assert result.exit_code == 0, result.output
    assert sample_task in result.output
    assert "Sample task" in result.output
    assert re.search(r"60m.*30m", result.output)
    assert "0.833" in result.output
    assert "—" in result.output
    assert "None" not in result.output
    assert not re.search(r"\d\.\d{4,}", result.output)
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", result.output)
    assert not any(character in result.output for character in "┌├└│")
    assert all(len(line) <= width for line in result.output.splitlines())


@pytest.mark.parametrize(
    "args",
    [
        ("focus",),
        ("goals", "list"),
        ("skills", "list"),
        ("skills", "history", "python"),
        ("insights",),
        ("analysis",),
        ("memory", "list"),
        ("ls",),
    ],
)
def test_empty_collections_do_not_render_empty_tables(test_db: Path, args: tuple[str, ...]) -> None:
    result = invoke(test_db, *args)
    assert result.exit_code == 0, result.output
    assert result.output.strip()
    assert not any(character in result.output for character in "┏┡└┃")
    assert TaskRepository(test_db).list_tasks() == []


def test_focus_without_skill_gaps_renders_only_ready_work(test_db: Path, sample_task: str) -> None:
    result = invoke(test_db, "focus")
    assert result.exit_code == 0, result.output
    assert "Sample task" in result.output
    assert sample_task in result.output
    assert result.output.count("┏") == 1


def test_insights_without_samples_has_no_python_representations(test_db: Path) -> None:
    result = invoke(test_db, "insights", "--category", "coding")
    assert result.exit_code == 0, result.output
    assert "coding" in result.output
    assert "no" in result.output
    assert "—" in result.output
    assert not any(value in result.output for value in ("None", "True", "False"))
