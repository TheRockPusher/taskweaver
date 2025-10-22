"""Tests for task repository."""

from pathlib import Path
from uuid import uuid4

import pytest

from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.exceptions import TaskNotFoundError
from taskweaver.database.models import TaskCreate, TaskStatus, TaskUpdate, TaskWithDependencies, TaskWithPriority
from taskweaver.database.repository import TaskRepository


def test_create_task(task_repo: TaskRepository) -> None:
    """Test creating a task."""
    task_data = TaskCreate(
        title="Test task",
        description="Test description",
        duration_min=30,
        llm_value=50.0,
        requirement="Test requirement",
    )
    task = task_repo.create_task(task_data)

    assert task.title == "Test task"
    assert task.description == "Test description"
    assert task.status == TaskStatus.PENDING
    assert task.task_id is not None


def test_get_task_by_id(task_repo: TaskRepository) -> None:
    """Test retrieving task by ID."""
    task_data = TaskCreate(title="Test task", duration_min=30, llm_value=50.0, requirement="Test requirement")
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
    task_repo.create_task(TaskCreate(title="Task 1", duration_min=30, llm_value=50.0, requirement="Test requirement"))
    task_repo.create_task(TaskCreate(title="Task 2", duration_min=30, llm_value=50.0, requirement="Test requirement"))
    task_repo.create_task(TaskCreate(title="Task 3", duration_min=30, llm_value=50.0, requirement="Test requirement"))

    tasks = task_repo.list_tasks()

    expected_count = 3
    assert len(tasks) == expected_count
    # Should be ordered by created_at DESC
    assert tasks[0].title == "Task 3"


def test_list_tasks_by_status(task_repo: TaskRepository) -> None:
    """Test filtering tasks by status."""
    task1 = task_repo.create_task(
        TaskCreate(title="Task 1", duration_min=30, llm_value=50.0, requirement="Test requirement")
    )
    task2 = task_repo.create_task(
        TaskCreate(title="Task 2", duration_min=30, llm_value=50.0, requirement="Test requirement")
    )
    task3 = task_repo.create_task(
        TaskCreate(title="Task 3", duration_min=30, llm_value=50.0, requirement="Test requirement")
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
    task_data = TaskCreate(title="Original title", duration_min=30, llm_value=50.0, requirement="Test requirement")
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
    task_data = TaskCreate(title="Task to complete", duration_min=30, llm_value=50.0, requirement="Test requirement")
    created_task = task_repo.create_task(task_data)

    updated_task = task_repo.mark_completed(created_task.task_id)

    assert updated_task.status == TaskStatus.COMPLETED


def test_mark_in_progress(task_repo: TaskRepository) -> None:
    """Test marking task as in progress."""
    task_data = TaskCreate(title="Task to start", duration_min=30, llm_value=50.0, requirement="Test requirement")
    created_task = task_repo.create_task(task_data)

    updated_task = task_repo.mark_in_progress(created_task.task_id)

    assert updated_task.status == TaskStatus.IN_PROGRESS


def test_mark_cancelled(task_repo: TaskRepository) -> None:
    """Test marking task as cancelled."""
    task_data = TaskCreate(title="Task to cancel", duration_min=30, llm_value=50.0, requirement="Test requirement")
    created_task = task_repo.create_task(task_data)

    updated_task = task_repo.mark_cancelled(created_task.task_id)

    assert updated_task.status == TaskStatus.CANCELLED


def test_delete_task(task_repo: TaskRepository) -> None:
    """Test deleting a task."""
    task_data = TaskCreate(title="Task to delete", duration_min=30, llm_value=50.0, requirement="Test requirement")
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
    task_data = TaskCreate(title="Auto-init test", duration_min=30, llm_value=50.0, requirement="Test requirement")
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
        TaskCreate(title="Quick win", duration_min=30, llm_value=90.0, requirement="Complete fast task")
    )
    assert quick_win.priority == 90.0 / 30  # 3.0

    # Low value, long duration = low priority
    long_grind = task_repo.create_task(
        TaskCreate(title="Long grind", duration_min=240, llm_value=30.0, requirement="Complete slow task")
    )
    assert long_grind.priority == 30.0 / 240  # 0.125

    # Verify priority changes when updating duration or value
    task_data = TaskCreate(title="Adjustable task", duration_min=60, llm_value=60.0, requirement="Initial requirement")
    task = task_repo.create_task(task_data)
    initial_priority = task.priority
    assert initial_priority == 60.0 / 60  # 1.0

    # Update duration - priority should change
    updated_task = task_repo.update_task(task.task_id, TaskUpdate(duration_min=30))
    assert updated_task.priority == 60.0 / 30  # 2.0 (doubled because duration halved)

    # Update value - priority should change
    updated_task = task_repo.update_task(task.task_id, TaskUpdate(llm_value=90.0))
    assert updated_task.priority == 90.0 / 30  # 3.0

    # Edge case: minimum duration (1 minute)
    max_priority_task = task_repo.create_task(
        TaskCreate(title="Ultra priority", duration_min=1, llm_value=100.0, requirement="Instant win")
    )
    max_prio = 100.0
    assert max_priority_task.priority == max_prio  # Maximum possible priority


def test_task_with_dependencies_is_blocked() -> None:
    """Test TaskWithDependencies.is_blocked property."""
    # Task with no blockers
    unblocked_task = TaskWithDependencies(
        title="Unblocked task",
        duration_min=30,
        llm_value=50.0,
        requirement="No blockers",
        active_blocker_count=0,
    )
    assert unblocked_task.is_blocked is False

    # Task with active blockers
    blocked_task = TaskWithDependencies(
        title="Blocked task",
        duration_min=30,
        llm_value=50.0,
        requirement="Has blockers",
        active_blocker_count=2,
    )
    assert blocked_task.is_blocked is True


def test_task_with_dependencies_is_blocking_others() -> None:
    """Test TaskWithDependencies.is_blocking_others property."""
    # Task blocking no others
    non_blocking_task = TaskWithDependencies(
        title="Non-blocking task",
        duration_min=30,
        llm_value=50.0,
        requirement="Blocks nothing",
        tasks_blocked_count=0,
    )
    assert non_blocking_task.is_blocking_others is False

    # Task blocking others
    blocking_task = TaskWithDependencies(
        title="Blocking task",
        duration_min=30,
        llm_value=50.0,
        requirement="Blocks others",
        tasks_blocked_count=3,
    )
    assert blocking_task.is_blocking_others is True


def test_effective_priority_no_dependencies(task_repo: TaskRepository) -> None:
    """Test effective priority equals intrinsic when no dependencies."""
    dep_repo = TaskDependencyRepository(task_repo.db_path)

    task = task_repo.create_task(
        TaskCreate(title="Solo task", duration_min=60, llm_value=60.0, requirement="Test requirement")
    )

    priorities = dep_repo.calculate_effective_priorities()
    effective = priorities[task.task_id]

    # No dependencies = effective priority equals intrinsic
    assert effective == task.priority  # 60.0 / 60 = 1.0


def test_effective_priority_inherits_from_blocked_task(task_repo: TaskRepository) -> None:
    """Test that blocker inherits priority from high-priority blocked task."""
    dep_repo = TaskDependencyRepository(task_repo.db_path)

    # Low priority blocker
    blocker = task_repo.create_task(
        TaskCreate(title="Setup CI", duration_min=120, llm_value=30.0, requirement="Test requirement")
    )
    # blocker.priority = 30.0 / 120 = 0.25

    # High priority task blocked by blocker
    blocked = task_repo.create_task(
        TaskCreate(title="Fix critical bug", duration_min=30, llm_value=90.0, requirement="Test requirement")
    )
    # blocked.priority = 90.0 / 30 = 3.0

    # Create dependency: blocked is blocked by blocker
    dep_repo.add_dependency(blocked.task_id, blocker.task_id)

    # Blocker should inherit high priority from blocked task
    priorities = dep_repo.calculate_effective_priorities()
    effective = priorities[blocker.task_id]
    assert effective == 3.0  # noqa: PLR2004 - Inherited from blocked task
    assert effective > blocker.priority  # 3.0 > 0.25


def test_effective_priority_chain_inheritance(task_repo: TaskRepository) -> None:
    """Test priority inheritance through chain: A blocks B blocks C."""
    dep_repo = TaskDependencyRepository(task_repo.db_path)

    # Task A: Low priority (0.5)
    task_a = task_repo.create_task(
        TaskCreate(title="Task A", duration_min=100, llm_value=50.0, requirement="Test requirement")
    )

    # Task B: Medium priority (0.7)
    task_b = task_repo.create_task(
        TaskCreate(title="Task B", duration_min=100, llm_value=70.0, requirement="Test requirement")
    )

    # Task C: High priority (1.0)
    task_c = task_repo.create_task(
        TaskCreate(title="Task C", duration_min=100, llm_value=100.0, requirement="Test requirement")
    )

    # Chain: A blocks B blocks C
    dep_repo.add_dependency(task_b.task_id, task_a.task_id)
    dep_repo.add_dependency(task_c.task_id, task_b.task_id)

    # A should inherit C's priority through B
    priorities = dep_repo.calculate_effective_priorities()
    effective_a = priorities[task_a.task_id]
    effective_b = priorities[task_b.task_id]
    effective_c = priorities[task_c.task_id]

    assert effective_c == 1.0
    assert effective_b == 1.0
    assert effective_a == 1.0


def test_effective_priority_batch_calculation(task_repo: TaskRepository) -> None:
    """Test batch calculation of all priorities in one pass."""
    dep_repo = TaskDependencyRepository(task_repo.db_path)

    # Create two tasks
    blocker = task_repo.create_task(
        TaskCreate(title="Blocker", duration_min=100, llm_value=100.0, requirement="Test requirement")
    )
    blocked = task_repo.create_task(
        TaskCreate(title="Blocked", duration_min=50, llm_value=100.0, requirement="Test requirement")
    )

    dep_repo.add_dependency(blocked.task_id, blocker.task_id)

    # Calculate all priorities at once
    priorities = dep_repo.calculate_effective_priorities()

    # Both tasks should be in result
    assert blocker.task_id in priorities
    assert blocked.task_id in priorities

    # Blocker inherits from blocked
    assert priorities[blocker.task_id] == 2.0  # noqa: PLR2004 - 100.0/50
    assert priorities[blocked.task_id] == 2.0  # noqa: PLR2004 - Its own priority


def test_effective_priority_multiple_blocked_tasks(task_repo: TaskRepository) -> None:
    """Test blocker inherits max priority when blocking multiple tasks."""
    dep_repo = TaskDependencyRepository(task_repo.db_path)

    # One blocker
    blocker = task_repo.create_task(
        TaskCreate(title="Blocker", duration_min=100, llm_value=50.0, requirement="Test requirement")
    )  # priority = 0.5

    # Three blocked tasks with different priorities
    blocked1 = task_repo.create_task(
        TaskCreate(title="Blocked 1", duration_min=200, llm_value=100.0, requirement="Test requirement")
    )  # priority = 0.5

    blocked2 = task_repo.create_task(
        TaskCreate(title="Blocked 2", duration_min=50, llm_value=100.0, requirement="Test requirement")
    )  # priority = 2.0

    blocked3 = task_repo.create_task(
        TaskCreate(title="Blocked 3", duration_min=100, llm_value=100.0, requirement="Test requirement")
    )  # priority = 1.0

    # All blocked by same blocker
    dep_repo.add_dependency(blocked1.task_id, blocker.task_id)
    dep_repo.add_dependency(blocked2.task_id, blocker.task_id)
    dep_repo.add_dependency(blocked3.task_id, blocker.task_id)

    # Blocker should inherit max priority (2.0 from blocked2)
    priorities = dep_repo.calculate_effective_priorities()
    effective = priorities[blocker.task_id]
    assert effective == 2.0  # noqa: PLR2004


def test_list_tasks_with_priority(task_repo: TaskRepository) -> None:
    """Test listing tasks with TaskWithPriority model."""
    dep_repo = TaskDependencyRepository(task_repo.db_path)

    # Create tasks
    blocker = task_repo.create_task(
        TaskCreate(title="Blocker", duration_min=100, llm_value=50.0, requirement="Test requirement")
    )
    blocked = task_repo.create_task(
        TaskCreate(title="Blocked", duration_min=50, llm_value=100.0, requirement="Test requirement")
    )

    dep_repo.add_dependency(blocked.task_id, blocker.task_id)

    # Get all tasks with priorities
    tasks_with_priority = dep_repo.list_tasks_with_priority()

    # Should return TaskWithPriority instances
    assert len(tasks_with_priority) == 2  # noqa: PLR2004
    assert all(isinstance(t, TaskWithPriority) for t in tasks_with_priority)

    # Find blocker task
    blocker_enriched = next(t for t in tasks_with_priority if t.task_id == blocker.task_id)

    # Should have all fields
    assert blocker_enriched.task_id == blocker.task_id
    assert blocker_enriched.tasks_blocked_count == 1  # Blocks 1 task
    assert blocker_enriched.active_blocker_count == 0  # Not blocked
    assert blocker_enriched.priority == 0.5  # noqa: PLR2004 - Intrinsic (50/100)
    assert blocker_enriched.effective_priority == 2.0  # noqa: PLR2004 - Inherited from blocked (100/50)

    # Can easily compare intrinsic vs effective
    assert blocker_enriched.effective_priority > blocker_enriched.priority
