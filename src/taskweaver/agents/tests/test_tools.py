"""Tests for agent tools."""

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.tools import (
    get_task_details_tool,
    list_tasks_tool,
    search_tasks_tool,
    update_task_status_tool,
    update_task_tool,
)
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import get_connection, init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.models import Task, TaskCreate, TaskStatus
from taskweaver.database.repository import TaskRepository


@pytest.fixture
def deps(db_path: Path) -> TaskDependencies:
    """Create TaskDependencies with repositories."""
    init_database(db_path)
    return TaskDependencies(
        task_repo=TaskRepository(db_path),
        dep_repo=TaskDependencyRepository(db_path),
        completion_repo=CompletionRepository(db_path),
        memories="",
        user_id="test_user",
    )


@pytest.fixture
def ctx(deps: TaskDependencies) -> RunContext[TaskDependencies]:
    """Create mock RunContext with dependencies."""

    class MockContext:
        def __init__(self, dependencies: TaskDependencies):
            self.deps = dependencies

    return MockContext(deps)  # type: ignore[return-value]


@pytest.fixture
def sample_task(deps: TaskDependencies) -> Task:
    """Create a sample task for testing."""
    task_data = TaskCreate(
        title="Test Task",
        description="Test description",
        duration_min=60,
        llm_value=75.0,
        requirement="Must work",
    )
    return deps.task_repo.create_task(task_data)


class TestUpdateTaskTool:
    """Tests for update_task_tool."""

    def test_update_task_success(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test updating task with valid data."""
        result = update_task_tool(ctx, sample_task.task_id, title="Updated Title", duration_min=90)

        assert result.title == "Updated Title"
        assert result.duration_min == 90
        assert result.task_id == sample_task.task_id

    def test_update_task_status(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test updating task status."""
        result = update_task_tool(ctx, sample_task.task_id, status="in_progress")

        assert result.status is TaskStatus.IN_PROGRESS

    def test_update_task_not_found(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test update with non-existent task raises ModelRetry."""
        fake_id = uuid4()
        with pytest.raises(ModelRetry):
            update_task_tool(ctx, fake_id, title="New Title")

    def test_update_task_invalid_status(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test update with invalid status raises ModelRetry."""
        with pytest.raises(ModelRetry):
            update_task_tool(ctx, sample_task.task_id, status="invalid_status")


class TestListTasksTool:
    """Tests for list_tasks_tool (backward compatibility)."""

    def test_list_all_tasks(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test listing all tasks returns concise format by default."""
        result = list_tasks_tool(ctx)

        assert isinstance(result, str)
        assert "Found 1 task" in result
        assert sample_task.title in result
        assert f"Status: {sample_task.status.value}" in result
        assert "TaskStatus." not in result

    def test_list_tasks_by_status(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:  # noqa: ARG002
        """Test listing tasks filtered by status."""
        result = list_tasks_tool(ctx, status="pending", response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) == 1
        assert result["tasks"][0].status is TaskStatus.PENDING
        assert result["tasks"][0].model_dump(mode="json")["status"] == "pending"

    def test_list_tasks_empty_filter(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test listing with filter that matches no tasks."""
        task_data = TaskCreate(
            title="Test Task",
            duration_min=30,
            llm_value=50.0,
            requirement="Requirement",
        )
        task = ctx.deps.task_repo.create_task(task_data)
        ctx.deps.task_repo.mark_completed(task.task_id)

        result = list_tasks_tool(ctx, status="pending")

        assert isinstance(result, str)
        assert "No tasks found" in result

    def test_list_tasks_multiple(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test listing multiple tasks."""
        for i in range(3):
            ctx.deps.task_repo.create_task(
                TaskCreate(
                    title=f"Task {i}",
                    duration_min=30,
                    llm_value=50.0,
                    requirement=f"Req {i}",
                )
            )

        result = list_tasks_tool(ctx, response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) == 3


class TestGetTaskDetailsTool:
    """Tests for get_task_details_tool."""

    def test_get_existing_task(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test retrieving existing task details."""
        result = get_task_details_tool(ctx, sample_task.task_id)

        assert isinstance(result, Task)
        assert result.task_id == sample_task.task_id
        assert result.title == sample_task.title

    def test_get_nonexistent_task(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test retrieving non-existent task raises ModelRetry."""
        fake_id = uuid4()

        with pytest.raises(ModelRetry, match="not found"):
            get_task_details_tool(ctx, fake_id)


class TestListTasksPagination:
    """Tests for list_tasks_tool pagination."""

    def test_pagination_first_page(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test first page returns correct limit."""
        # Create 25 tasks
        for i in range(25):
            ctx.deps.task_repo.create_task(
                TaskCreate(title=f"Task {i}", duration_min=30, llm_value=50.0, requirement=f"Req {i}")
            )

        result = list_tasks_tool(ctx, limit=10, offset=0, response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) == 10
        assert result["total_count"] == 25
        assert result["has_more"] is True

    def test_pagination_last_page(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test last page has fewer results."""
        for i in range(25):
            ctx.deps.task_repo.create_task(
                TaskCreate(title=f"Task {i}", duration_min=30, llm_value=50.0, requirement=f"Req {i}")
            )

        result = list_tasks_tool(ctx, limit=10, offset=20, response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) == 5
        assert result["has_more"] is False

    def test_max_limit_enforced(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test limit capped at 50."""
        for i in range(60):
            ctx.deps.task_repo.create_task(
                TaskCreate(title=f"Task {i}", duration_min=30, llm_value=50.0, requirement=f"Req {i}")
            )

        result = list_tasks_tool(ctx, limit=100, response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) <= 50

    def test_concise_format_returns_string(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test concise format returns summary string."""
        result = list_tasks_tool(ctx, response_format="concise")

        assert isinstance(result, str)
        assert "Found 1 task" in result
        assert sample_task.title in result
        assert f"Status: {sample_task.status.value}" in result
        assert "TaskStatus." not in result

    def test_invalid_sort_by_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test invalid sort_by raises ModelRetry."""
        with pytest.raises(ModelRetry, match="Invalid sort_by"):
            list_tasks_tool(ctx, sort_by="invalid")

    def test_invalid_response_format_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test invalid response_format raises ModelRetry."""
        with pytest.raises(ModelRetry, match="Invalid response_format"):
            list_tasks_tool(ctx, response_format="xml")


class TestSearchTasksTool:
    """Tests for search_tasks_tool."""

    def test_search_by_title(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test searching tasks by title keyword."""
        ctx.deps.task_repo.create_task(
            TaskCreate(title="Build login feature", duration_min=120, llm_value=80.0, requirement="OAuth2")
        )
        ctx.deps.task_repo.create_task(
            TaskCreate(title="Fix logout bug", duration_min=30, llm_value=60.0, requirement="Session")
        )

        result = search_tasks_tool(ctx, "login", response_format="detailed")

        assert isinstance(result, dict)
        assert result["total_matches"] == 1
        assert "login" in result["tasks"][0].title.lower()

    def test_search_by_requirement(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test searching tasks by requirement field."""

        ctx.deps.task_repo.create_task(
            TaskCreate(title="Setup auth", duration_min=60, llm_value=75.0, requirement="OAuth2 implementation")
        )

        result = search_tasks_tool(ctx, "OAuth2", response_format="detailed")

        assert isinstance(result, dict)
        assert result["total_matches"] == 1

    def test_search_concise_status(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Search summaries expose the status value, not the enum representation."""
        result = search_tasks_tool(ctx, sample_task.title, status="pending")

        assert isinstance(result, str)
        assert f"Status: {sample_task.status.value}" in result
        assert "TaskStatus." not in result

    def test_search_no_matches(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test search with no matching tasks."""

        ctx.deps.task_repo.create_task(
            TaskCreate(title="Build feature", duration_min=60, llm_value=70.0, requirement="Test")
        )

        result = search_tasks_tool(ctx, "nonexistent", response_format="concise")

        assert isinstance(result, str)
        assert "No tasks found" in result

    def test_search_empty_query_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test empty query raises ModelRetry."""

        with pytest.raises(ModelRetry, match="cannot be empty"):
            search_tasks_tool(ctx, "")

    def test_search_with_min_priority(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test search with priority filter."""

        ctx.deps.task_repo.create_task(
            TaskCreate(title="High priority task", duration_min=30, llm_value=90.0, requirement="Test")
        )
        ctx.deps.task_repo.create_task(
            TaskCreate(title="Low priority task", duration_min=120, llm_value=30.0, requirement="Test")
        )

        result = search_tasks_tool(ctx, "task", min_priority=2.0, response_format="detailed")

        assert isinstance(result, dict)
        assert result["total_matches"] == 1
        assert result["tasks"][0].priority >= 2.0


class TestUpdateTaskStatusTool:
    """Tests for consolidated update_task_status_tool."""

    def test_mark_in_progress(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test marking task as in_progress."""

        result = update_task_status_tool(ctx, sample_task.task_id, "in_progress")

        assert "in progress" in result.lower()
        task = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert task is not None
        assert task.status == TaskStatus.IN_PROGRESS

    def test_mark_completed_without_tracking(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test marking task completed without duration."""

        result = update_task_status_tool(ctx, sample_task.task_id, "completed")

        assert "completed" in result.lower()
        completion = ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id)
        assert completion is None

    def test_mark_completed_with_tracking(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test marking task completed with duration tracking."""

        result = update_task_status_tool(ctx, sample_task.task_id, "completed", duration_actual=90)

        assert "90min actual" in result
        assert "variance" in result.lower()
        completion = ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id)
        assert completion is not None
        assert completion.duration_actual == 90

    def test_mark_cancelled(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test marking task cancelled."""

        result = update_task_status_tool(ctx, sample_task.task_id, "cancelled")

        assert "cancelled" in result.lower()
        task = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert task is not None
        assert task.status == TaskStatus.CANCELLED

    def test_invalid_status_raises(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test invalid status raises ModelRetry."""

        with pytest.raises(ModelRetry, match="Invalid new_status"):
            update_task_status_tool(ctx, sample_task.task_id, "invalid")

    def test_nonexistent_task_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test non-existent task raises ModelRetry."""

        with pytest.raises(ModelRetry, match="not found"):
            update_task_status_tool(ctx, uuid4(), "completed")

    @pytest.mark.parametrize("status", ["completed", "cancelled"])
    def test_tracked_closure_snapshots_dependencies(
        self, ctx: RunContext[TaskDependencies], sample_task: Task, status: str
    ) -> None:
        """The consolidated tool captures blocker evidence before cleanup."""
        downstream = ctx.deps.task_repo.create_task(
            TaskCreate(title="Downstream", duration_min=30, llm_value=80.0, requirement="Needs sample task")
        )
        ctx.deps.dep_repo.add_dependency(downstream.task_id, sample_task.task_id)

        update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90, conclusion="Measured time")

        completion = ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id)
        assert completion is not None
        assert completion.status.value == status
        assert completion.duration_actual == 90
        assert completion.duration_expected == sample_task.duration_min
        assert completion.raw_duration_min == sample_task.raw_duration_min
        assert completion.category == sample_task.category
        assert completion.conclusion == "Measured time"
        assert completion.priority_factors is not None
        assert completion.priority_factors["dependencies"] > 0
        assert ctx.deps.dep_repo.get_blockers(downstream.task_id) == []

    @pytest.mark.parametrize("status", ["completed", "cancelled"])
    def test_tracked_closure_failure_preserves_task_and_edges(
        self, ctx: RunContext[TaskDependencies], sample_task: Task, status: str
    ) -> None:
        """Cleanup failures propagate and roll back the complete closure transaction."""
        downstream = ctx.deps.task_repo.create_task(
            TaskCreate(title="Downstream", duration_min=30, llm_value=80.0, requirement="Needs sample task")
        )
        ctx.deps.dep_repo.add_dependency(downstream.task_id, sample_task.task_id)
        with get_connection(ctx.deps.task_repo.db_path) as conn, conn:
            conn.execute(
                """CREATE TRIGGER reject_cleanup BEFORE DELETE ON task_dependencies
                   BEGIN SELECT RAISE(ABORT, 'cleanup refused'); END"""
            )

        with pytest.raises(sqlite3.IntegrityError, match="cleanup refused"):
            update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90)

        unchanged = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert unchanged is not None
        assert unchanged.status == TaskStatus.PENDING
        assert ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id) is None
        assert [task.task_id for task in ctx.deps.dep_repo.get_blockers(downstream.task_id)] == [sample_task.task_id]

    @pytest.mark.parametrize("status", ["completed", "cancelled"])
    def test_completion_retries_are_idempotent_and_conflicts_become_model_retry(
        self, ctx: RunContext[TaskDependencies], sample_task: Task, status: str
    ) -> None:
        """Correct retries reuse evidence; conflicting requests never rewrite it."""
        update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90, conclusion="Measured time")
        original = ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id)
        assert original is not None

        update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90, conclusion="Measured time")
        assert ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id) == original

        with pytest.raises(ModelRetry, match="Conflicting completion"):
            update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=100, conclusion="Measured time")
        with pytest.raises(ModelRetry, match="Conflicting completion"):
            update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90, conclusion="Changed notes")
        other_status = "cancelled" if status == "completed" else "completed"
        with pytest.raises(ModelRetry, match="different status"):
            update_task_status_tool(
                ctx, sample_task.task_id, other_status, duration_actual=90, conclusion="Measured time"
            )

        assert ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id) == original
        closed = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert closed is not None
        assert closed.status.value == status

    @pytest.mark.parametrize("status", ["completed", "cancelled"])
    def test_untracked_closure_creates_no_completion_evidence(
        self, ctx: RunContext[TaskDependencies], sample_task: Task, status: str
    ) -> None:
        """A closure without measured time changes status without inventing evidence."""
        update_task_status_tool(ctx, sample_task.task_id, status, conclusion="No measured time")

        closed = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert closed is not None
        assert closed.status.value == status
        assert ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id) is None
