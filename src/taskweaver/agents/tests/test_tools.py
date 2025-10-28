"""Tests for agent tools."""

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.tools import (
    get_task_details_tool,
    list_open_tasks_dep_count_tool,
    list_tasks_tool,
    update_task_tool,
)
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import init_database
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

        assert result.status == TaskStatus.IN_PROGRESS

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
    """Tests for list_tasks_tool."""

    def test_list_all_tasks(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test listing all tasks without filter."""
        result = list_tasks_tool(ctx)

        assert len(result) == 1
        assert result[0].task_id == sample_task.task_id

    def test_list_tasks_by_status(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:  # noqa: ARG002
        """Test listing tasks filtered by status."""
        result = list_tasks_tool(ctx, status="pending")

        assert len(result) == 1
        assert result[0].status == TaskStatus.PENDING

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

        assert len(result) == 0

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

        result = list_tasks_tool(ctx)

        assert len(result) == 3


class TestGetTaskDetailsTool:
    """Tests for get_task_details_tool."""

    def test_get_existing_task(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test retrieving existing task details."""
        result = get_task_details_tool(ctx, sample_task.task_id)

        assert isinstance(result, Task)
        assert result.task_id == sample_task.task_id
        assert result.title == sample_task.title

    def test_get_nonexistent_task(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test retrieving non-existent task returns error message."""
        fake_id = uuid4()
        result = get_task_details_tool(ctx, fake_id)

        assert isinstance(result, str)
        assert "not found" in result.lower()
        assert str(fake_id) in result


class TestListOpenTasksDepCountTool:
    """Tests for list_open_tasks_dep_count_tool."""

    def test_list_open_tasks_with_deps(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test listing open tasks with dependency counts."""
        task1_data = TaskCreate(
            title="Task 1",
            duration_min=30,
            llm_value=50.0,
            requirement="Requirement 1",
        )
        task2_data = TaskCreate(
            title="Task 2",
            duration_min=60,
            llm_value=75.0,
            requirement="Requirement 2",
        )

        task1 = ctx.deps.task_repo.create_task(task1_data)
        task2 = ctx.deps.task_repo.create_task(task2_data)
        ctx.deps.dep_repo.add_dependency(task2.task_id, task1.task_id)

        result = list_open_tasks_dep_count_tool(ctx)

        assert len(result) == 2
        assert all(hasattr(task, "active_blocker_count") for task in result)
        assert all(hasattr(task, "tasks_blocked_count") for task in result)

    def test_list_open_tasks_empty(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test listing when no open tasks exist."""
        result = list_open_tasks_dep_count_tool(ctx)

        assert len(result) == 0
