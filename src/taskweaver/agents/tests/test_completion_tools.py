"""Tests for completion tracking in agent tools."""

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.models import CompletionStatus, TaskCreate, TaskUpdate
from taskweaver.database.repository import TaskRepository

from ..dependencies import TaskDependencies
from ..tools import mark_task_cancelled_tool, mark_task_completed_tool


@pytest.fixture
def deps(db_path: Path) -> TaskDependencies:
    """Create TaskDependencies for testing.

    Args:
        db_path: Temporary database path.

    Returns:
        TaskDependencies instance with all repositories.
    """
    # Initialize database
    init_database(db_path)

    return TaskDependencies(
        task_repo=TaskRepository(db_path),
        dep_repo=TaskDependencyRepository(db_path),
        completion_repo=CompletionRepository(db_path),
        memories="",
        user_id="test_user",
    )


@pytest.fixture
def mock_ctx(deps: TaskDependencies) -> RunContext[TaskDependencies]:
    """Create mock RunContext for testing.

    Args:
        deps: TaskDependencies instance.

    Returns:
        Mock RunContext with dependencies.
    """

    class MockContext:
        def __init__(self, dependencies: TaskDependencies):
            self.deps = dependencies

    return MockContext(deps)  # type: ignore[return-value]


def test_mark_completed_without_tracking(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking task completed without duration tracking."""
    # Create a task
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Complete test")
    )

    # Mark completed without tracking
    result = mark_task_completed_tool(mock_ctx, task.task_id)

    assert "✅ Task 'Test task' marked as completed" in result
    assert "📊 Completion tracked" not in result

    # Verify no completion record created
    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion is None


def test_mark_completed_with_tracking(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking task completed with duration tracking."""
    # Create a task
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Complete test")
    )

    # Mark completed with tracking
    result = mark_task_completed_tool(mock_ctx, task.task_id, duration_actual=90)

    assert "✅ Completed 'Test task'" in result
    assert "60min estimated" in result
    assert "90min actual" in result
    assert "+50.0% variance" in result

    # Verify completion record created
    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion is not None
    assert completion.status == CompletionStatus.COMPLETED
    assert completion.duration_expected == 60
    assert completion.duration_actual == 90
    assert completion.variance_minutes == 30
    assert completion.variance_percent == 50.0


def test_mark_completed_with_conclusion(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking task completed with duration and conclusion."""
    # Create a task
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Test task", duration_min=120, llm_value=85.0, requirement="Complete test")
    )

    # Mark completed with tracking and conclusion
    result = mark_task_completed_tool(
        mock_ctx, task.task_id, duration_actual=150, conclusion="Took longer due to complexity"
    )

    assert "✅ Completed 'Test task'" in result
    assert "120min estimated" in result
    assert "150min actual" in result
    assert "+25.0% variance" in result

    # Verify completion record with conclusion
    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion is not None
    assert completion.conclusion == "Took longer due to complexity"


def test_mark_completed_under_estimate(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking task completed when actual time is less than estimate."""
    # Create a task
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Fast task", duration_min=120, llm_value=80.0, requirement="Complete test")
    )

    # Mark completed with less time than estimated
    result = mark_task_completed_tool(mock_ctx, task.task_id, duration_actual=60)

    assert "✅ Completed 'Fast task'" in result
    assert "120min estimated" in result
    assert "60min actual" in result
    assert "-50.0% variance" in result  # Negative variance (took less time)

    # Verify completion record
    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion is not None
    assert completion.variance_minutes == -60
    assert completion.variance_percent == -50.0


def test_mark_cancelled_without_tracking(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking task cancelled without duration tracking."""
    # Create a task
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Cancelled task", duration_min=60, llm_value=50.0, requirement="Test requirement")
    )

    # Mark cancelled without tracking
    result = mark_task_cancelled_tool(mock_ctx, task.task_id)

    assert "❌ Task 'Cancelled task' marked as cancelled" in result
    assert "📊 Cancellation tracked" not in result

    # Verify no completion record created
    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion is None


def test_mark_cancelled_with_tracking(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking task cancelled with duration tracking."""
    # Create a task
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Cancelled task", duration_min=60, llm_value=50.0, requirement="Test requirement")
    )

    # Mark cancelled with tracking
    result = mark_task_cancelled_tool(mock_ctx, task.task_id, duration_actual=30)

    assert "❌ Cancelled 'Cancelled task'" in result
    assert "spent 30min" in result

    # Verify completion record created with cancelled status
    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion is not None
    assert completion.status == CompletionStatus.CANCELLED
    assert completion.duration_expected == 60
    assert completion.duration_actual == 30


def test_mark_cancelled_with_reason(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking task cancelled with reason."""
    # Create a task
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Cancelled task", duration_min=120, llm_value=70.0, requirement="Test requirement")
    )

    # Mark cancelled with tracking and reason
    result = mark_task_cancelled_tool(mock_ctx, task.task_id, duration_actual=45, conclusion="Requirements changed")

    assert "❌ Cancelled 'Cancelled task'" in result
    assert "spent 45min" in result

    # Verify completion record with conclusion
    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion is not None
    assert completion.conclusion == "Requirements changed"


def test_mark_completed_nonexistent_task(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking non-existent task completed raises ModelRetry."""
    with pytest.raises(ModelRetry, match="Task not found"):
        mark_task_completed_tool(mock_ctx, uuid4())


def test_mark_cancelled_nonexistent_task(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking non-existent task cancelled raises ModelRetry."""
    with pytest.raises(ModelRetry, match="Task not found"):
        mark_task_cancelled_tool(mock_ctx, uuid4())


def test_completion_immutable_snapshot(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test that completion stores immutable snapshot of duration_expected."""
    # Create task with duration_min=60
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Test requirement")
    )

    # Complete with tracking (snapshot duration_expected=60)
    mark_task_completed_tool(mock_ctx, task.task_id, duration_actual=120)

    # Get completion record
    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion is not None
    assert completion.duration_expected == 60

    # Update task duration_min to 120 (reflecting learning)
    mock_ctx.deps.task_repo.update_task(task.task_id, TaskUpdate(duration_min=120))

    # Completion snapshot should remain unchanged
    completion_after = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion_after is not None
    assert completion_after.duration_expected == 60  # Frozen snapshot, not 120

    # Task updated but completion unchanged
    updated_task = mock_ctx.deps.task_repo.get_task(task.task_id)
    assert updated_task is not None
    assert updated_task.duration_min == 120
    assert completion_after.duration_expected == 60
