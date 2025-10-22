"""Tests for task repository."""

from pathlib import Path
from uuid import uuid4

import pytest

from taskweaver.database.exceptions import TaskNotFoundError
from taskweaver.database.models import TaskCreate, TaskStatus, TaskUpdate
from taskweaver.database.repository import TaskRepository


def test_create_task(task_repo: TaskRepository) -> None:
    """Test creating a task."""
    task_data = TaskCreate(
        title="Test task",
        description="Test description",
        duration_min=30,
        llm_value=5.0,
        requirement="Test requirement",
    )
    task = task_repo.create_task(task_data)

    assert task.title == "Test task"
    assert task.description == "Test description"
    assert task.status == TaskStatus.PENDING
    assert task.task_id is not None


def test_get_task_by_id(task_repo: TaskRepository) -> None:
    """Test retrieving task by ID."""
    task_data = TaskCreate(title="Test task", duration_min=30, llm_value=5.0, requirement="Test requirement")
    created_task = task_repo.create_task(task_data)

    retrieved_task = task_repo.get_task(created_task.task_id)

    assert retrieved_task is not None
    assert retrieved_task.task_id == created_task.task_id
    assert retrieved_task.title == created_task.title


def test_get_nonexistent_task(task_repo: TaskRepository) -> None:
    """Test retrieving non-existent task returns None."""
    task = task_repo.get_task(uuid4())
    assert task is None


def test_list_all_tasks(task_repo: TaskRepository) -> None:
    """Test listing all tasks."""
    task_repo.create_task(TaskCreate(title="Task 1", duration_min=30, llm_value=5.0, requirement="Test requirement"))
    task_repo.create_task(TaskCreate(title="Task 2", duration_min=30, llm_value=5.0, requirement="Test requirement"))
    task_repo.create_task(TaskCreate(title="Task 3", duration_min=30, llm_value=5.0, requirement="Test requirement"))

    tasks = task_repo.list_tasks()

    expected_count = 3
    assert len(tasks) == expected_count
    # Should be ordered by created_at DESC
    assert tasks[0].title == "Task 3"


def test_list_tasks_by_status(task_repo: TaskRepository) -> None:
    """Test filtering tasks by status."""
    task1 = task_repo.create_task(
        TaskCreate(title="Task 1", duration_min=30, llm_value=5.0, requirement="Test requirement")
    )
    task2 = task_repo.create_task(
        TaskCreate(title="Task 2", duration_min=30, llm_value=5.0, requirement="Test requirement")
    )
    task3 = task_repo.create_task(
        TaskCreate(title="Task 3", duration_min=30, llm_value=5.0, requirement="Test requirement")
    )

    # Mark some as completed
    task_repo.mark_completed(task1.task_id)
    task_repo.mark_in_progress(task2.task_id)

    # List pending tasks
    pending = task_repo.list_tasks(status=TaskStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].task_id == task3.task_id

    # List completed tasks
    completed = task_repo.list_tasks(status=TaskStatus.COMPLETED)
    assert len(completed) == 1
    assert completed[0].task_id == task1.task_id

    # List in progress tasks
    in_progress = task_repo.list_tasks(status=TaskStatus.IN_PROGRESS)
    assert len(in_progress) == 1
    assert in_progress[0].task_id == task2.task_id


def test_update_task(task_repo: TaskRepository) -> None:
    """Test updating a task."""
    task_data = TaskCreate(title="Original title", duration_min=30, llm_value=5.0, requirement="Test requirement")
    created_task = task_repo.create_task(task_data)

    update_data = TaskUpdate(title="Updated title", status=TaskStatus.IN_PROGRESS)
    updated_task = task_repo.update_task(created_task.task_id, update_data)

    assert updated_task.title == "Updated title"
    assert updated_task.status == TaskStatus.IN_PROGRESS
    assert updated_task.updated_at > created_task.updated_at


def test_update_nonexistent_task(task_repo: TaskRepository) -> None:
    """Test updating non-existent task raises TaskNotFoundError."""
    update_data = TaskUpdate(title="New title")

    with pytest.raises(TaskNotFoundError) as exc_info:
        task_repo.update_task(uuid4(), update_data)

    assert "Task not found" in str(exc_info.value)


def test_mark_completed(task_repo: TaskRepository) -> None:
    """Test marking task as completed."""
    task_data = TaskCreate(title="Task to complete", duration_min=30, llm_value=5.0, requirement="Test requirement")
    created_task = task_repo.create_task(task_data)

    updated_task = task_repo.mark_completed(created_task.task_id)

    assert updated_task.status == TaskStatus.COMPLETED


def test_mark_in_progress(task_repo: TaskRepository) -> None:
    """Test marking task as in progress."""
    task_data = TaskCreate(title="Task to start", duration_min=30, llm_value=5.0, requirement="Test requirement")
    created_task = task_repo.create_task(task_data)

    updated_task = task_repo.mark_in_progress(created_task.task_id)

    assert updated_task.status == TaskStatus.IN_PROGRESS


def test_mark_cancelled(task_repo: TaskRepository) -> None:
    """Test marking task as cancelled."""
    task_data = TaskCreate(title="Task to cancel", duration_min=30, llm_value=5.0, requirement="Test requirement")
    created_task = task_repo.create_task(task_data)

    updated_task = task_repo.mark_cancelled(created_task.task_id)

    assert updated_task.status == TaskStatus.CANCELLED


def test_delete_task(task_repo: TaskRepository) -> None:
    """Test deleting a task."""
    task_data = TaskCreate(title="Task to delete", duration_min=30, llm_value=5.0, requirement="Test requirement")
    created_task = task_repo.create_task(task_data)

    task_repo.delete_task(created_task.task_id)

    # Verify it's gone
    task = task_repo.get_task(created_task.task_id)
    assert task is None


def test_mark_completed_nonexistent_task(task_repo: TaskRepository) -> None:
    """Test marking non-existent task as completed raises TaskNotFoundError."""
    with pytest.raises(TaskNotFoundError) as exc_info:
        task_repo.mark_completed(uuid4())

    assert "Task not found" in str(exc_info.value)


def test_mark_in_progress_nonexistent_task(task_repo: TaskRepository) -> None:
    """Test marking non-existent task as in progress raises TaskNotFoundError."""
    with pytest.raises(TaskNotFoundError) as exc_info:
        task_repo.mark_in_progress(uuid4())

    assert "Task not found" in str(exc_info.value)


def test_mark_cancelled_nonexistent_task(task_repo: TaskRepository) -> None:
    """Test marking non-existent task as cancelled raises TaskNotFoundError."""
    with pytest.raises(TaskNotFoundError) as exc_info:
        task_repo.mark_cancelled(uuid4())

    assert "Task not found" in str(exc_info.value)


def test_delete_nonexistent_task(task_repo: TaskRepository) -> None:
    """Test deleting non-existent task raises TaskNotFoundError."""
    with pytest.raises(TaskNotFoundError) as exc_info:
        task_repo.delete_task(uuid4())

    assert "Task not found" in str(exc_info.value)


def test_auto_initialize_database(tmp_path: Path) -> None:
    """Test that database auto-initializes on first use."""
    db_path = tmp_path / "auto_init.db"

    # Verify database doesn't exist yet
    assert not db_path.exists()

    # Create repository - should auto-initialize
    repo = TaskRepository(db_path)

    # Create a task - should work without manual init
    task_data = TaskCreate(title="Auto-init test", duration_min=30, llm_value=5.0, requirement="Test requirement")
    task = repo.create_task(task_data)

    # Verify database was created and task exists
    assert db_path.exists()
    assert task.title == "Auto-init test"

    # Verify we can retrieve the task
    retrieved = repo.get_task(task.task_id)
    assert retrieved is not None
    assert retrieved.task_id == task.task_id


def test_task_priority_calculation(task_repo: TaskRepository) -> None:
    """Test that priority is correctly calculated as llm_value / duration_min."""
    # High value, short duration = high priority
    quick_win = task_repo.create_task(
        TaskCreate(title="Quick win", duration_min=30, llm_value=9.0, requirement="Complete fast task")
    )
    assert quick_win.priority == 9.0 / 30  # 0.3

    # Low value, long duration = low priority
    long_grind = task_repo.create_task(
        TaskCreate(title="Long grind", duration_min=240, llm_value=3.0, requirement="Complete slow task")
    )
    assert long_grind.priority == 3.0 / 240  # 0.0125

    # Verify priority changes when updating duration or value
    task_data = TaskCreate(title="Adjustable task", duration_min=60, llm_value=6.0, requirement="Initial requirement")
    task = task_repo.create_task(task_data)
    initial_priority = task.priority
    assert initial_priority == 6.0 / 60  # 0.1

    # Update duration - priority should change
    updated_task = task_repo.update_task(task.task_id, TaskUpdate(duration_min=30))
    assert updated_task.priority == 6.0 / 30  # 0.2 (doubled because duration halved)

    # Update value - priority should change
    updated_task = task_repo.update_task(task.task_id, TaskUpdate(llm_value=9.0))
    assert updated_task.priority == 9.0 / 30  # 0.3

    # Edge case: minimum duration (1 minute)
    max_priority_task = task_repo.create_task(
        TaskCreate(title="Ultra priority", duration_min=1, llm_value=10.0, requirement="Instant win")
    )
    assert max_priority_task.priority == 10.0  # Maximum possible priority
