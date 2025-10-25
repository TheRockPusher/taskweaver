"""Tests for completion repository."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.exceptions import CompletionNotFoundError
from taskweaver.database.models import CompletionCreate, CompletionStatus, TaskCreate, TaskUpdate
from taskweaver.database.repository import TaskRepository


def test_create_completion(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test creating a completion record."""
    # Create a task first
    task = task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Complete test")
    )

    # Create completion
    completion_data = CompletionCreate(
        task_id=task.task_id,
        status=CompletionStatus.COMPLETED,
        duration_expected=60,
        duration_actual=75,
        conclusion="Task took longer than expected due to scope creep",
    )
    completion = completion_repo.create_completion(completion_data)

    assert completion.task_id == task.task_id
    assert completion.status == CompletionStatus.COMPLETED
    assert completion.duration_expected == 60
    assert completion.duration_actual == 75
    assert completion.conclusion == "Task took longer than expected due to scope creep"
    assert completion.completion_id is not None


def test_create_completion_cancelled_status(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test creating a completion with cancelled status."""
    task = task_repo.create_task(
        TaskCreate(title="Cancelled task", duration_min=60, llm_value=50.0, requirement="Test requirement")
    )

    completion_data = CompletionCreate(
        task_id=task.task_id,
        status=CompletionStatus.CANCELLED,
        duration_expected=60,
        duration_actual=30,
        conclusion="Task cancelled due to changing requirements",
    )
    completion = completion_repo.create_completion(completion_data)

    assert completion.status == CompletionStatus.CANCELLED
    assert completion.duration_actual == 30


def test_get_completion_by_id(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test retrieving completion by completion_id."""
    task = task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )

    created_completion = completion_repo.create_completion(
        CompletionCreate(
            task_id=task.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=65
        )
    )

    retrieved_completion = completion_repo.get_completion(created_completion.completion_id)

    assert retrieved_completion is not None
    assert retrieved_completion.completion_id == created_completion.completion_id
    assert retrieved_completion.task_id == task.task_id


def test_get_nonexistent_completion(completion_repo: CompletionRepository) -> None:
    """Test retrieving non-existent completion returns None."""
    completion = completion_repo.get_completion(uuid4())
    assert completion is None


def test_get_completion_by_task_id(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test retrieving completion by task_id."""
    task = task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )

    created_completion = completion_repo.create_completion(
        CompletionCreate(
            task_id=task.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=70
        )
    )

    retrieved_completion = completion_repo.get_completion_by_task_id(task.task_id)

    assert retrieved_completion is not None
    assert retrieved_completion.task_id == task.task_id
    assert retrieved_completion.completion_id == created_completion.completion_id


def test_get_completion_by_task_id_nonexistent(completion_repo: CompletionRepository) -> None:
    """Test retrieving completion for non-existent task returns None."""
    completion = completion_repo.get_completion_by_task_id(uuid4())
    assert completion is None


def test_list_all_completions(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test listing all completions."""
    # Create tasks and completions
    task1 = task_repo.create_task(
        TaskCreate(title="Task 1", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )
    task2 = task_repo.create_task(
        TaskCreate(title="Task 2", duration_min=90, llm_value=70.0, requirement="Test requirement")
    )
    task3 = task_repo.create_task(
        TaskCreate(title="Task 3", duration_min=120, llm_value=90.0, requirement="Test requirement")
    )

    completion_repo.create_completion(
        CompletionCreate(
            task_id=task1.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=65
        )
    )
    completion_repo.create_completion(
        CompletionCreate(
            task_id=task2.task_id, status=CompletionStatus.COMPLETED, duration_expected=90, duration_actual=85
        )
    )
    completion_repo.create_completion(
        CompletionCreate(
            task_id=task3.task_id, status=CompletionStatus.CANCELLED, duration_expected=120, duration_actual=30
        )
    )

    completions = completion_repo.list_completions()

    expected_count = 3
    assert len(completions) == expected_count
    # Should be ordered by closed_at DESC (most recent first)
    assert completions[0].task_id == task3.task_id


def test_list_completions_by_status(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test filtering completions by status."""
    task1 = task_repo.create_task(
        TaskCreate(title="Task 1", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )
    task2 = task_repo.create_task(
        TaskCreate(title="Task 2", duration_min=90, llm_value=70.0, requirement="Test requirement")
    )
    task3 = task_repo.create_task(
        TaskCreate(title="Task 3", duration_min=120, llm_value=90.0, requirement="Test requirement")
    )

    completion1 = completion_repo.create_completion(
        CompletionCreate(
            task_id=task1.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=65
        )
    )
    completion_repo.create_completion(
        CompletionCreate(
            task_id=task2.task_id, status=CompletionStatus.CANCELLED, duration_expected=90, duration_actual=30
        )
    )
    completion3 = completion_repo.create_completion(
        CompletionCreate(
            task_id=task3.task_id, status=CompletionStatus.COMPLETED, duration_expected=120, duration_actual=130
        )
    )

    # List completed
    completed = completion_repo.list_completions(status=CompletionStatus.COMPLETED)
    assert len(completed) == 2
    assert all(c.status == CompletionStatus.COMPLETED for c in completed)
    assert {c.completion_id for c in completed} == {completion1.completion_id, completion3.completion_id}

    # List cancelled
    cancelled = completion_repo.list_completions(status=CompletionStatus.CANCELLED)
    assert len(cancelled) == 1
    assert cancelled[0].status == CompletionStatus.CANCELLED


def test_delete_completion(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test deleting a completion record."""
    task = task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )

    created_completion = completion_repo.create_completion(
        CompletionCreate(
            task_id=task.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=70
        )
    )

    completion_repo.delete_completion(created_completion.completion_id)

    # Verify it's gone
    completion = completion_repo.get_completion(created_completion.completion_id)
    assert completion is None


def test_delete_nonexistent_completion(completion_repo: CompletionRepository) -> None:
    """Test deleting non-existent completion raises CompletionNotFoundError."""
    with pytest.raises(CompletionNotFoundError) as exc_info:
        completion_repo.delete_completion(uuid4())

    assert "Completion not found" in str(exc_info.value)


def test_completion_variance_minutes(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test variance_minutes property calculation."""
    task = task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )

    # Over-estimate (took longer than expected)
    completion = completion_repo.create_completion(
        CompletionCreate(
            task_id=task.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=90
        )
    )
    assert completion.variance_minutes == 30  # 90 - 60

    # Under-estimate (took less than expected)
    task2 = task_repo.create_task(
        TaskCreate(title="Task 2", duration_min=120, llm_value=80.0, requirement="Test requirement")
    )
    completion2 = completion_repo.create_completion(
        CompletionCreate(
            task_id=task2.task_id, status=CompletionStatus.COMPLETED, duration_expected=120, duration_actual=90
        )
    )
    assert completion2.variance_minutes == -30  # 90 - 120

    # Perfect estimate
    task3 = task_repo.create_task(
        TaskCreate(title="Task 3", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )
    completion3 = completion_repo.create_completion(
        CompletionCreate(
            task_id=task3.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=60
        )
    )
    assert completion3.variance_minutes == 0


def test_completion_variance_percent(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test variance_percent property calculation."""
    task = task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )

    # 100% over (took 2x longer)
    completion = completion_repo.create_completion(
        CompletionCreate(
            task_id=task.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=120
        )
    )
    assert completion.variance_percent == 100.0

    # 50% over
    task2 = task_repo.create_task(
        TaskCreate(title="Task 2", duration_min=100, llm_value=80.0, requirement="Test requirement")
    )
    completion2 = completion_repo.create_completion(
        CompletionCreate(
            task_id=task2.task_id, status=CompletionStatus.COMPLETED, duration_expected=100, duration_actual=150
        )
    )
    assert completion2.variance_percent == 50.0

    # -50% (took half the time)
    task3 = task_repo.create_task(
        TaskCreate(title="Task 3", duration_min=100, llm_value=80.0, requirement="Test requirement")
    )
    completion3 = completion_repo.create_completion(
        CompletionCreate(
            task_id=task3.task_id, status=CompletionStatus.COMPLETED, duration_expected=100, duration_actual=50
        )
    )
    assert completion3.variance_percent == -50.0


def test_completion_retroactive_recording(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test retroactive completion recording with custom closed_at."""
    task = task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )

    # Complete task yesterday
    yesterday = datetime.now(UTC) - timedelta(days=1)
    completion = completion_repo.create_completion(
        CompletionCreate(
            task_id=task.task_id,
            status=CompletionStatus.COMPLETED,
            closed_at=yesterday,
            duration_expected=60,
            duration_actual=70,
        )
    )

    # closed_at should be yesterday, created_at should be now
    assert completion.closed_at < completion.created_at
    assert (completion.created_at - completion.closed_at).days >= 1


def test_auto_initialize_database(tmp_path: Path) -> None:
    """Test that completion table auto-initializes on first use."""
    db_path = tmp_path / "auto_init.db"

    # Verify database doesn't exist yet
    assert not db_path.exists()

    # Create repository - should auto-initialize
    task_repo = TaskRepository(db_path)
    completion_repo = CompletionRepository(db_path)

    # Create task and completion - should work without manual init
    task = task_repo.create_task(
        TaskCreate(title="Auto-init test", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )
    completion = completion_repo.create_completion(
        CompletionCreate(
            task_id=task.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=65
        )
    )

    # Verify database was created and completion exists
    assert db_path.exists()
    assert completion.task_id == task.task_id

    # Verify we can retrieve the completion
    retrieved = completion_repo.get_completion(completion.completion_id)
    assert retrieved is not None
    assert retrieved.completion_id == completion.completion_id


def test_completion_immutable_snapshot(completion_repo: CompletionRepository, task_repo: TaskRepository) -> None:
    """Test that completion stores immutable snapshot of duration_expected."""
    # Create task with duration_min=60
    task = task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )

    # Complete task (snapshot duration_expected=60)
    completion = completion_repo.create_completion(
        CompletionCreate(
            task_id=task.task_id, status=CompletionStatus.COMPLETED, duration_expected=60, duration_actual=120
        )
    )
    assert completion.duration_expected == 60

    # Update task duration_min to 120 (reflecting learning)
    task_repo.update_task(task.task_id, TaskUpdate(duration_min=120))

    # Completion snapshot should remain unchanged
    retrieved_completion = completion_repo.get_completion(completion.completion_id)
    assert retrieved_completion is not None
    assert retrieved_completion.duration_expected == 60  # Frozen snapshot, not 120

    # This proves duration_expected is stored, not referenced
    updated_task = task_repo.get_task(task.task_id)
    assert updated_task is not None
    assert updated_task.duration_min == 120  # Task updated
    assert retrieved_completion.duration_expected == 60  # Completion unchanged
