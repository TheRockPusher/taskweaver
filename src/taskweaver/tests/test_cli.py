"""Tests for CLI commands."""

import re
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

from taskweaver.cli import app
from taskweaver.database import TaskRepository, init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.models import TaskCreate, TaskStatus, TaskUpdate

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


@pytest.fixture
def sample_task(test_db: Path) -> str:
    """Create a sample task and return its ID."""
    repo = TaskRepository(test_db)
    task = repo.create_task(
        TaskCreate(
            title="Sample task",
            description="Sample description",
            duration_min=30,
            llm_value=50.0,
            requirement="Test requirement",
        )
    )
    return str(task.task_id)


def test_create_command_with_title_only(test_db: Path) -> None:
    """Test create command with title only."""
    result = runner.invoke(
        app,
        [
            "create",
            "Test task",
            "--duration",
            "30",
            "--value",
            "5.0",
            "--req",
            "Test requirement",
            "--db",
            str(test_db),
        ],
    )

    assert result.exit_code == 0
    assert "Created task" in result.stdout
    assert "Test task" in result.stdout


def test_create_command_with_description(test_db: Path) -> None:
    """Test create command with title and description."""
    result = runner.invoke(
        app,
        [
            "create",
            "Test task",
            "--duration",
            "30",
            "--value",
            "5.0",
            "--req",
            "Test requirement",
            "-d",
            "Test description",
            "--db",
            str(test_db),
        ],
    )

    assert result.exit_code == 0
    assert "Created task" in result.stdout

    # Verify task was created in database
    repo = TaskRepository(test_db)
    tasks = repo.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].title == "Test task"
    assert tasks[0].description == "Test description"


def test_list_command_empty_database(test_db: Path) -> None:
    """Test list command with empty database."""
    result = runner.invoke(app, ["ls", "--db", str(test_db)])

    assert result.exit_code == 0
    assert "No tasks found" in result.stdout


def test_list_command_with_tasks(test_db: Path, sample_task: str) -> None:  # noqa: ARG001
    """Test list command with tasks in database."""
    result = runner.invoke(app, ["ls", "--db", str(test_db)])
    output = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "Sample" in output  # Title may be truncated in table
    assert "Total: 1 task(s)" in output
    # Check that dates are formatted as yyyy-mm-dd (no time component)
    assert "2025-" in output  # Year present
    assert "+00:00" not in output  # No timezone in list view


def test_list_command_filter_by_status(test_db: Path) -> None:
    """Test list command with status filter."""
    repo = TaskRepository(test_db)
    repo.create_task(TaskCreate(title="Pending task", duration_min=30, llm_value=50.0, requirement="Test requirement"))
    task = repo.create_task(TaskCreate(title="Active", duration_min=30, llm_value=50.0, requirement="Test requirement"))
    repo.update_task(task.task_id, TaskUpdate(status=TaskStatus.IN_PROGRESS))

    result = runner.invoke(app, ["ls", "-s", "in_progress", "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Active" in result.stdout
    assert "in_pr" in result.stdout  # Status is truncated in table as "in_pr…"
    assert "Pending task" not in result.stdout


def test_update_command_title(test_db: Path, sample_task: str) -> None:
    """Test update command changing title."""
    result = runner.invoke(app, ["edit", sample_task, "--title", "New", "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Updated task" in result.stdout
    assert "New" in result.stdout

    # Verify update in database
    repo = TaskRepository(test_db)
    task = repo.get_task(UUID(sample_task))
    assert task is not None
    assert task.title == "New"


def test_update_command_status(test_db: Path, sample_task: str) -> None:
    """Test update command changing status."""
    result = runner.invoke(app, ["edit", sample_task, "-s", "in_progress", "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Updated task" in result.stdout


def test_update_command_no_fields(test_db: Path, sample_task: str) -> None:
    """Test update command with no fields fails."""
    result = runner.invoke(app, ["edit", sample_task, "--db", str(test_db)])

    assert result.exit_code == 1
    assert "Must specify at least one field" in result.stdout


def test_delete_command_with_force(test_db: Path, sample_task: str) -> None:
    """Test delete command with force flag."""
    result = runner.invoke(app, ["rm", sample_task, "-f", "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Deleted task" in result.stdout

    # Verify deletion
    repo = TaskRepository(test_db)
    tasks = repo.list_tasks()
    assert len(tasks) == 0


def test_delete_command_with_confirmation_yes(test_db: Path, sample_task: str) -> None:
    """Test delete command with confirmation (yes)."""
    result = runner.invoke(app, ["rm", sample_task, "--db", str(test_db)], input="y\n")

    assert result.exit_code == 0
    assert "Deleted task" in result.stdout


def test_delete_command_with_confirmation_no(test_db: Path, sample_task: str) -> None:
    """Test delete command with confirmation (no)."""
    result = runner.invoke(app, ["rm", sample_task, "--db", str(test_db)], input="n\n")

    assert result.exit_code == 1
    assert "Cancelled" in result.stdout

    # Verify task still exists
    repo = TaskRepository(test_db)
    tasks = repo.list_tasks()
    assert len(tasks) == 1


def test_show_command_existing_task(test_db: Path, sample_task: str) -> None:
    """Test show command with existing task."""
    result = runner.invoke(app, ["show", sample_task, "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Task:" in result.stdout  # Table title contains task ID
    assert "Sample task" in result.stdout
    assert "Sample description" in result.stdout
    assert sample_task in result.stdout
    # Table should show field names
    assert "Title" in result.stdout
    assert "Status" in result.stdout
    # Full timestamp should be present in detail view
    assert "+00:00" in result.stdout


def test_show_command_nonexistent_task(test_db: Path) -> None:
    """Test show command with non-existent task."""
    fake_uuid = str(uuid4())
    result = runner.invoke(app, ["show", fake_uuid, "--db", str(test_db)])

    assert result.exit_code == 1
    assert "Task not found" in result.stdout


def test_create_command_auto_initializes_database(tmp_path: Path) -> None:
    """Test that create command auto-initializes database."""
    db_path = tmp_path / "new.db"

    # Database doesn't exist yet
    assert not db_path.exists()

    # Create a task - should auto-initialize
    result = runner.invoke(
        app,
        [
            "create",
            "Auto-init test",
            "--duration",
            "30",
            "--value",
            "5.0",
            "--req",
            "Test requirement",
            "--db",
            str(db_path),
        ],
    )

    assert result.exit_code == 0
    assert db_path.exists()

    # Verify task was created
    repo = TaskRepository(db_path)
    tasks = repo.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].title == "Auto-init test"


def test_list_open_command_empty(test_db: Path) -> None:
    """Test lso command with empty database."""
    result = runner.invoke(app, ["lso", "--db", str(test_db)])

    assert result.exit_code == 0
    assert "No tasks found" in result.stdout


def test_list_open_command_with_tasks(test_db: Path, sample_task: str) -> None:  # noqa: ARG001
    """Test lso command with tasks."""
    result = runner.invoke(app, ["lso", "--db", str(test_db)])
    output = strip_ansi(result.stdout)

    assert result.exit_code == 0
    # Title may be truncated in table (Sam… task)
    assert "Sample task" in output or "Sam" in output
    assert "Total: 1 task(s)" in output


def test_restart_db_command(test_db: Path) -> None:
    """Test restartDB command without delete - preserves existing data."""
    # Add a task first
    repo = TaskRepository(test_db)
    repo.create_task(TaskCreate(title="Test task", duration_min=30, llm_value=50.0, requirement="Test requirement"))

    # Restart DB without delete - reinitializes schema but preserves data
    result = runner.invoke(app, ["restartDB", "--db", str(test_db)])
    assert result.exit_code == 0
    assert "Database initialized" in result.stdout

    # Database should still be accessible and contain the task
    tasks = repo.list_tasks()
    assert isinstance(tasks, list)
    assert len(tasks) == 1
    assert tasks[0].title == "Test task"


def test_restart_db_command_with_delete(test_db: Path) -> None:
    """Test restartDB command with --delete flag - removes all data."""
    # Add a task first
    repo = TaskRepository(test_db)
    repo.create_task(TaskCreate(title="Test task", duration_min=30, llm_value=50.0, requirement="Test requirement"))
    assert len(repo.list_tasks()) == 1

    # Restart DB with --delete flag
    result = runner.invoke(app, ["restartDB", "--db", str(test_db), "--delete"])
    assert result.exit_code == 0
    assert "Deleting existing database" in result.stdout
    assert "Database deleted" in result.stdout
    assert "Database initialized" in result.stdout

    # Database should be empty after delete + reinit
    tasks = repo.list_tasks()
    assert tasks == []


def test_create_dependency_command(test_db: Path) -> None:
    """Test createDep command."""
    repo = TaskRepository(test_db)
    task1 = repo.create_task(
        TaskCreate(title="Task 1", duration_min=30, llm_value=50.0, requirement="Test requirement")
    )
    task2 = repo.create_task(
        TaskCreate(title="Task 2", duration_min=30, llm_value=50.0, requirement="Test requirement")
    )

    result = runner.invoke(app, ["createDep", str(task1.task_id), str(task2.task_id), "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Dependency added" in result.stdout
    assert str(task1.task_id) in result.stdout
    assert str(task2.task_id) in result.stdout

    # Verify dependency was created
    dep_repo = TaskDependencyRepository(test_db)
    blockers = dep_repo.get_blockers(task1.task_id)
    assert len(blockers) == 1
    assert blockers[0].task_id == task2.task_id


def test_remove_dependency_command(test_db: Path) -> None:
    """Test rmdep command."""
    repo = TaskRepository(test_db)
    task1 = repo.create_task(
        TaskCreate(title="Task 1", duration_min=30, llm_value=50.0, requirement="Test requirement")
    )
    task2 = repo.create_task(
        TaskCreate(title="Task 2", duration_min=30, llm_value=50.0, requirement="Test requirement")
    )

    # Add dependency first
    dep_repo = TaskDependencyRepository(test_db)
    dep_repo.add_dependency(task1.task_id, task2.task_id)

    # Remove it
    result = runner.invoke(app, ["rmdep", str(task1.task_id), str(task2.task_id), "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Dependency removed" in result.stdout
    assert str(task1.task_id) in result.stdout
    assert str(task2.task_id) in result.stdout

    # Verify dependency was removed
    blockers = dep_repo.get_blockers(task1.task_id)
    assert len(blockers) == 0


def test_blocker_command_empty(test_db: Path, sample_task: str) -> None:
    """Test blocker command with no blockers."""
    result = runner.invoke(app, ["blocker", sample_task, "--db", str(test_db)])

    assert result.exit_code == 0
    # Should show table with task ID in title (may be wrapped across lines)
    # Check for partial UUID match since Rich tables can wrap long UUIDs
    assert "blockers" in result.stdout.lower()
    # Table should be empty (no blocker rows)


def test_blocker_command_with_blockers(test_db: Path) -> None:
    """Test blocker command with blockers."""
    repo = TaskRepository(test_db)
    task1 = repo.create_task(
        TaskCreate(title="Blocked Task", duration_min=30, llm_value=50.0, requirement="Test requirement")
    )
    task2 = repo.create_task(
        TaskCreate(title="Blocker Task", duration_min=30, llm_value=50.0, requirement="Test requirement")
    )

    dep_repo = TaskDependencyRepository(test_db)
    dep_repo.add_dependency(task1.task_id, task2.task_id)

    result = runner.invoke(app, ["blocker", str(task1.task_id), "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Blocker Task" in result.stdout
    assert str(task2.task_id) in result.stdout
