"""Agent tools for task management operations.

This module defines PydanticAI tools that wrap TaskRepository methods,
providing a clean interface for the orchestrator agent to interact with tasks.

Error Handling Strategy:
- ModelRetry: Raised when tool fails due to invalid input that LLM can fix
  (circular dependencies, invalid task IDs, validation errors)
- The LLM receives the error message and can retry with corrected parameters
"""

from uuid import UUID

from pydantic import ValidationError
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from taskweaver.database.exceptions import DependencyError, TaskNotFoundError
from taskweaver.database.models import TaskDependency, TaskWithDependencies

from ..database.models import Task, TaskCreate, TaskStatus
from .dependencies import TaskDependencies

# Display constants
MAX_TITLE_LENGTH = 60
MAX_DESCRIPTION_LENGTH = 40


def create_task_tool(  # noqa: PLR0913
    ctx: RunContext[TaskDependencies],
    title: str,
    duration_min: int,
    llm_value: float,
    requirement: str,
    description: str | None = None,
) -> str:
    """Create a new task with required fields.

    Use this tool when user wants to add a task to their task list.
    Validates title length (1-500 chars) and returns task ID for future reference.

    Args:
        ctx: Runtime context containing TaskDependencies.
        title: Task title (1-500 characters). Be specific and actionable.
        duration_min: Estimated duration in minutes (must be >= 1).
        llm_value: LLM-assigned value score (0-10 scale).
        requirement: Task requirement or conclusion field (1-500 characters).
        description: Optional task description for context.

    Returns:
        Confirmation message with task ID and title.

    Raises:
        ModelRetry: If validation fails. LLM receives error and can retry.

    Example:
        >>> create_task_tool(ctx, "Build login feature", 120, 8.5, "OAuth2 implementation", "Implement OAuth2")
        "✅ Created task 'Build login feature' (ID: 123e4567-...)"
    """
    try:
        task_data = TaskCreate(
            title=title,
            description=description,
            duration_min=duration_min,
            llm_value=llm_value,
            requirement=requirement,
        )
        task = ctx.deps.task_repo.create_task(task_data)
        return f"✅ Created task '{task.title}' (ID: {task.task_id})"
    except (ValidationError, ValueError) as e:
        raise ModelRetry(str(e)) from e


def list_tasks_tool(ctx: RunContext[TaskDependencies], status: str | None = None) -> list[Task]:
    """List all tasks or filter by status.

    Returns all tasks or filters by status to help user view workload.
    Use without status to get complete overview, or with status to focus on specific categories.

    Args:
        ctx: Runtime context containing TaskDependencies.
        status: Optional status filter. Valid values: 'pending', 'in_progress', 'completed', 'cancelled'.

    Returns:
        List of Task objects matching the filter (or all tasks if no filter).

    Example:
        >>> list_tasks_tool(ctx, status="pending")
        [Task(...), Task(...), ...]
    """
    # Parse status string to enum if provided
    task_status = TaskStatus(status) if status else None

    tasks: list[Task] = ctx.deps.task_repo.list_tasks(status=task_status)

    return tasks


def mark_task_completed_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> str:
    """Mark a task as completed.

    Transitions task to completed status and unblocks any tasks depending on it.
    Use when user confirms they've finished the task.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to mark as completed.

    Returns:
        Confirmation message with task title.

    Raises:
        ModelRetry: If task doesn't exist. LLM can retry with correct task ID.

    Example:
        >>> mark_task_completed_tool(ctx, UUID("123e4567-e89b-12d3-a456-426614174000"))
        "✅ Task 'Build login feature' marked as completed"
    """
    try:
        task = ctx.deps.task_repo.mark_completed(task_id)
        return f"✅ Task '{task.title}' marked as completed"
    except TaskNotFoundError as e:
        raise ModelRetry(str(e)) from e


def mark_task_in_progress_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> str:
    """Mark a task as in progress.

    Transitions task to in_progress status to track active work.
    Use when user starts working on a task.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to mark as in progress.

    Returns:
        Confirmation message with task title.

    Raises:
        ModelRetry: If task doesn't exist. LLM can retry with correct task ID.

    Example:
        >>> mark_task_in_progress_tool(ctx, UUID("123e4567-e89b-12d3-a456-426614174000"))
        "Task 'Build login feature' marked as in progress"
    """
    try:
        task = ctx.deps.task_repo.mark_in_progress(task_id)
        return f"Task '{task.title}' marked as in progress"
    except TaskNotFoundError as e:
        raise ModelRetry(str(e)) from e


def mark_task_cancelled_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> str:
    """Mark a task as cancelled.

    Transitions task to cancelled status to remove from active workload.
    Use when task is no longer needed or will not be completed.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to mark as cancelled.

    Returns:
        Confirmation message with task title.

    Raises:
        ModelRetry: If task doesn't exist. LLM can retry with correct task ID.

    Example:
        >>> mark_task_cancelled_tool(ctx, UUID("123e4567-e89b-12d3-a456-426614174000"))
        "❌ Task 'Build login feature' marked as cancelled"
    """
    try:
        task = ctx.deps.task_repo.mark_cancelled(task_id)
        return f"❌ Task '{task.title}' marked as cancelled"
    except TaskNotFoundError as e:
        raise ModelRetry(str(e)) from e


def get_task_details_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> Task | str:
    """Get detailed information about a specific task.

    Retrieves full task metadata including title, description, status, and timestamps.
    Use when user needs to see all details about a specific task.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to retrieve.

    Returns:
        Task object if found, error message string if not found.

    Example:
        >>> get_task_details_tool(ctx, UUID("123e4567-e89b-12d3-a456-426614174000"))
        Task(task_id=..., title='Build login feature', ...)
    """
    task: Task | None = ctx.deps.task_repo.get_task(task_id)

    if task is None:
        return f"❌ Task not found: {task_id}"

    return task


def list_open_tasks_dep_count_tool(ctx: RunContext[TaskDependencies]) -> list[TaskWithDependencies]:
    """List open tasks with dependency information.

    Retrieves all open (pending/in_progress) tasks with pre-calculated blocker
    and blocked counts from the tasks_full view. Helps identify ready tasks
    and tasks that are waiting for dependencies to complete.

    Args:
        ctx: Runtime context containing TaskDependencies.

    Returns:
        List of TaskWithDependencies objects including active_blocker_count
        and tasks_blocked_count for each task.

    Example:
        >>> list_open_tasks_dep_count_tool(ctx)
        [TaskWithDependencies(...), TaskWithDependencies(...), ...]
    """
    # Get all tasks with dependency counts from tasks_full view
    all_tasks: list[TaskWithDependencies] = ctx.deps.task_repo.list_tasks_with_deps()

    return all_tasks


def add_dependency_tool(ctx: RunContext[TaskDependencies], task_id: UUID, blocker_id: UUID) -> TaskDependency:
    """Create a dependency relationship between two tasks.

    Marks task_id as blocked by blocker_id, preventing task_id from being
    completed until blocker_id is done. Automatically detects and prevents cycles.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task that is being blocked.
        blocker_id: UUID of the task that blocks task_id.

    Returns:
        TaskDependency object representing the created relationship.

    Raises:
        ModelRetry: If cycle detected, blocker closed, duplicate exists, or tasks not found.
            LLM receives error and can retry with different task IDs.

    Example:
        >>> add_dependency_tool(ctx, task_id=UUID(...), blocker_id=UUID(...))
        TaskDependency(task_id=..., blocker_id=..., created_at=...)
    """
    try:
        return ctx.deps.dep_repo.add_dependency(task_id, blocker_id)
    except (DependencyError, TaskNotFoundError) as e:
        raise ModelRetry(str(e)) from e


def get_blockers_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> list[Task]:
    """Get all active tasks blocking a given task.

    Returns tasks that must be completed before task_id can proceed.
    Only includes active blockers (pending/in_progress), not completed/cancelled.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to check for blockers.

    Returns:
        List of Task objects that are actively blocking task_id (empty if unblocked).

    Raises:
        TaskNotFoundError: If task_id doesn't exist.

    Example:
        >>> get_blockers_tool(ctx, UUID("..."))
        [Task(title='Setup database', ...), Task(title='Configure auth', ...)]
    """
    return ctx.deps.dep_repo.get_blockers(task_id)


def get_blocked_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> list[Task]:
    """Get all tasks blocked by a given task.

    Returns tasks that are waiting for task_id to be completed.
    Helps identify the impact of completing a task.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to check for dependents.

    Returns:
        List of Task objects that are blocked by task_id (empty if blocking no tasks).

    Raises:
        TaskNotFoundError: If task_id doesn't exist.

    Example:
        >>> get_blocked_tool(ctx, UUID("..."))
        [Task(title='Deploy to production', ...), Task(title='Write documentation', ...)]
    """
    return ctx.deps.dep_repo.get_blocked(task_id)


def remove_dependency_tool(ctx: RunContext[TaskDependencies], task_id: UUID, blocker_id: UUID) -> str:
    """Remove a dependency relationship between two tasks.

    Unblocks task_id so it no longer depends on blocker_id being completed.
    Use when a dependency is no longer necessary or was incorrectly added.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task being unblocked.
        blocker_id: UUID of the task that no longer blocks task_id.

    Returns:
        Confirmation message with task IDs.

    Raises:
        ModelRetry: If dependency doesn't exist or tasks not found. LLM can retry.

    Example:
        >>> remove_dependency_tool(ctx, task_id=UUID(...), blocker_id=UUID(...))
        "Dependency between ... and ... removed"
    """
    try:
        ctx.deps.dep_repo.remove_dependency(task_id, blocker_id)
        return f"✅ Dependency removed: {task_id} no longer blocked by {blocker_id}"
    except (DependencyError, TaskNotFoundError) as e:
        raise ModelRetry(str(e)) from e
