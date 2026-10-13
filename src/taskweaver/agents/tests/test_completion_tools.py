"""Tests for completion tracking in agent tools."""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import get_connection, init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.models import CompletionStatus, Task, TaskCreate, TaskStatus, TaskUpdate
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


@pytest.fixture
def blocking_tasks(mock_ctx: RunContext[TaskDependencies]) -> tuple[Task, Task]:
    """Create a blocker with distinct working and raw duration snapshots."""
    blocker = mock_ctx.deps.task_repo.create_task(
        TaskCreate(
            title="Blocking task",
            duration_min=30,
            raw_duration_min=30,
            llm_value=80.0,
            requirement="Deliver prerequisite",
            category="engineering",
        )
    )
    blocker = mock_ctx.deps.task_repo.update_task(blocker.task_id, TaskUpdate(duration_min=60))
    downstream = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Downstream task", duration_min=30, llm_value=80.0, requirement="Use prerequisite")
    )
    mock_ctx.deps.dep_repo.add_dependency(downstream.task_id, blocker.task_id)
    return blocker, downstream


def test_mark_completed_with_tracking(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking task completed with duration tracking."""
    # Create a task
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Test task", duration_min=60, llm_value=80.0, requirement="Complete test")
    )

    # Mark completed with tracking
    result = mark_task_completed_tool(mock_ctx, task.task_id, duration_actual=90, conclusion="Delivered")

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
    assert completion.conclusion == "Delivered"
    assert completion.variance_minutes == 30
    assert completion.variance_percent == 50.0


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


def test_mark_cancelled_with_tracking(mock_ctx: RunContext[TaskDependencies]) -> None:
    """Test marking task cancelled with duration tracking."""
    # Create a task
    task = mock_ctx.deps.task_repo.create_task(
        TaskCreate(title="Cancelled task", duration_min=60, llm_value=50.0, requirement="Test requirement")
    )

    # Mark cancelled with tracking
    result = mark_task_cancelled_tool(mock_ctx, task.task_id, duration_actual=30, conclusion="Requirements changed")

    assert "❌ Cancelled 'Cancelled task'" in result
    assert "spent 30min" in result

    # Verify completion record created with cancelled status
    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(task.task_id)
    assert completion is not None
    assert completion.status == CompletionStatus.CANCELLED
    assert completion.duration_expected == 60
    assert completion.duration_actual == 30
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


@pytest.mark.parametrize("status", [CompletionStatus.COMPLETED, CompletionStatus.CANCELLED])
def test_tracked_closure_snapshots_blocker_before_cleanup(
    mock_ctx: RunContext[TaskDependencies], blocking_tasks: tuple[Task, Task], status: CompletionStatus
) -> None:
    """Real completion tools must preserve factors before removing blocker edges."""
    blocker, downstream = blocking_tasks
    tool = mark_task_completed_tool if status == CompletionStatus.COMPLETED else mark_task_cancelled_tool

    tool(mock_ctx, blocker.task_id, duration_actual=90, conclusion="Delivered prerequisite")

    completion = mock_ctx.deps.completion_repo.get_completion_by_task_id(blocker.task_id)
    assert completion is not None
    assert completion.status == status
    assert completion.duration_expected == 60
    assert completion.raw_duration_min == 30
    assert completion.category == "engineering"
    assert completion.duration_actual == 90
    assert completion.conclusion == "Delivered prerequisite"
    assert completion.priority_factors is not None
    assert completion.priority_factors["dependencies"] > 0
    closed = mock_ctx.deps.task_repo.get_task(blocker.task_id)
    assert closed is not None
    assert closed.status.value == status.value
    assert mock_ctx.deps.dep_repo.get_blockers(downstream.task_id) == []


@pytest.mark.parametrize("status", [CompletionStatus.COMPLETED, CompletionStatus.CANCELLED])
def test_tracked_closure_failure_rolls_back_record_status_and_edges(
    mock_ctx: RunContext[TaskDependencies], blocking_tasks: tuple[Task, Task], status: CompletionStatus
) -> None:
    """A failure during real dependency cleanup cannot partially close a task."""
    blocker, downstream = blocking_tasks
    tool = mark_task_completed_tool if status == CompletionStatus.COMPLETED else mark_task_cancelled_tool
    with get_connection(mock_ctx.deps.task_repo.db_path) as conn, conn:
        conn.execute(
            """CREATE TRIGGER reject_cleanup BEFORE DELETE ON task_dependencies
               BEGIN SELECT RAISE(ABORT, 'cleanup refused'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="cleanup refused"):
        tool(mock_ctx, blocker.task_id, duration_actual=90)

    unchanged = mock_ctx.deps.task_repo.get_task(blocker.task_id)
    assert unchanged is not None
    assert unchanged.status == TaskStatus.PENDING
    assert mock_ctx.deps.completion_repo.get_completion_by_task_id(blocker.task_id) is None
    assert [task.task_id for task in mock_ctx.deps.dep_repo.get_blockers(downstream.task_id)] == [blocker.task_id]


@pytest.mark.parametrize("status", [CompletionStatus.COMPLETED, CompletionStatus.CANCELLED])
def test_invalid_actual_duration_does_not_close_task(
    mock_ctx: RunContext[TaskDependencies], blocking_tasks: tuple[Task, Task], status: CompletionStatus
) -> None:
    """Input validation errors become retries without destroying task state."""
    blocker, downstream = blocking_tasks
    tool = mark_task_completed_tool if status == CompletionStatus.COMPLETED else mark_task_cancelled_tool

    with pytest.raises(ModelRetry):
        tool(mock_ctx, blocker.task_id, duration_actual=0)

    unchanged = mock_ctx.deps.task_repo.get_task(blocker.task_id)
    assert unchanged is not None
    assert unchanged.status == TaskStatus.PENDING
    assert mock_ctx.deps.completion_repo.get_completion_by_task_id(blocker.task_id) is None
    assert [task.task_id for task in mock_ctx.deps.dep_repo.get_blockers(downstream.task_id)] == [blocker.task_id]


@pytest.mark.parametrize("status", [CompletionStatus.COMPLETED, CompletionStatus.CANCELLED])
def test_untracked_closure_does_not_invent_actual_duration(
    mock_ctx: RunContext[TaskDependencies], blocking_tasks: tuple[Task, Task], status: CompletionStatus
) -> None:
    """A conclusion alone does not fabricate completion evidence."""
    blocker, downstream = blocking_tasks
    tool = mark_task_completed_tool if status == CompletionStatus.COMPLETED else mark_task_cancelled_tool

    tool(mock_ctx, blocker.task_id, conclusion="No measured time available")

    closed = mock_ctx.deps.task_repo.get_task(blocker.task_id)
    assert closed is not None
    assert closed.status.value == status.value
    assert mock_ctx.deps.completion_repo.get_completion_by_task_id(blocker.task_id) is None
    assert mock_ctx.deps.dep_repo.get_blockers(downstream.task_id) == []
