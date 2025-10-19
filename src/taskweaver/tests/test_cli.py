"""Tests for CLI commands."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

from taskweaver.cli import app
from taskweaver.database import TaskRepository, init_database
from taskweaver.database.models import TaskCreate, TaskStatus, TaskUpdate

runner = CliRunner()


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
    task = repo.create_task(TaskCreate(title="Sample task", description="Sample description"))
    return str(task.task_id)


def test_create_command_with_title_only(test_db: Path) -> None:
    """Test create command with title only."""
    result = runner.invoke(app, ["create", "Test task", "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Created task" in result.stdout
    assert "Test task" in result.stdout


def test_create_command_with_description(test_db: Path) -> None:
    """Test create command with title and description."""
    result = runner.invoke(app, ["create", "Test task", "-d", "Test description", "--db", str(test_db)])

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

    assert result.exit_code == 0
    assert "Sample task" in result.stdout
    assert "Total: 1 task(s)" in result.stdout
    # Check that dates are formatted as yyyy-mm-dd (no time component)
    assert "2025-" in result.stdout  # Year present
    assert "+00:00" not in result.stdout  # No timezone in list view


def test_list_command_filter_by_status(test_db: Path) -> None:
    """Test list command with status filter."""
    repo = TaskRepository(test_db)
    repo.create_task(TaskCreate(title="Pending task"))
    task = repo.create_task(TaskCreate(title="Active"))
    repo.update_task(task.task_id, TaskUpdate(status=TaskStatus.IN_PROGRESS))

    result = runner.invoke(app, ["ls", "-s", "in_progress", "--db", str(test_db)])

    assert result.exit_code == 0
    assert "Active" in result.stdout
    assert "in_progre" in result.stdout  # Status might be truncated in table
    assert "Pending task" not in result.stdout


def test_update_command_title(test_db: Path, sample_task: str) -> None:
    """Test update command changing title."""
    result = runner.invoke(app, ["edit", sample_task, "-t", "New", "--db", str(test_db)])

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
    result = runner.invoke(app, ["create", "Auto-init test", "--db", str(db_path)])

    assert result.exit_code == 0
    assert db_path.exists()

    # Verify task was created
    repo = TaskRepository(db_path)
    tasks = repo.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].title == "Auto-init test"
