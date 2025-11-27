"""Agent tools for task management operations.

This module defines PydanticAI tools that wrap TaskRepository methods,
providing a clean interface for the orchestrator agent to interact with tasks.

Error Handling Strategy:
- ModelRetry: Raised when tool fails due to invalid input that LLM can fix
    (circular dependencies, invalid task IDs, validation errors)
- The LLM receives the error message and can retry with corrected parameters
"""

from enum import Enum
from uuid import UUID

from pydantic import ValidationError
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from taskweaver.database.exceptions import DependencyError, TaskNotFoundError
from taskweaver.database.models import (
    CompletionCreate,
    CompletionStatus,
    TaskDependency,
    TaskWithPriority,
)

from ..database.models import Task, TaskCreate, TaskStatus, TaskUpdate
from .dependencies import TaskDependencies

# Display constants
MAX_TITLE_LENGTH = 60
MAX_DESCRIPTION_LENGTH = 40


class ResponseFormat(str, Enum):
    """Output format for tool results."""

    CONCISE = "concise"  # Human-readable summary (token-efficient)
    DETAILED = "detailed"  # Full structured data (for tool chaining)


def _format_task_concise(task: Task, index: int = 0) -> str:
    """Format task as concise single-line summary.

    Args:
        task: Task object to format.
        index: Display index (1-based for user display).

    Returns:
        Single-line task summary string.
    """
    idx_str = f"{index}. " if index > 0 else ""
    return (
        f"{idx_str}{task.title[:MAX_TITLE_LENGTH]} "
        f"(Status: {task.status}, Priority: {task.priority:.2f}, "
        f"Duration: {task.duration_min}min)"
    )


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
        llm_value: LLM-assigned value score (0-100 scale).
        requirement: Task requirement or conclusion field (1-500 characters).
        description: Optional task description for context.

    Returns:
        Confirmation message with task ID and title.

    Raises:
        ModelRetry: If validation fails. LLM receives error and can retry.

    Example:
        >>> create_task_tool(ctx, "Build login feature", 120, 85.0, "OAuth2 implementation", "Implement OAuth2")
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


def update_task_tool(  # noqa: PLR0913
    ctx: RunContext[TaskDependencies],
    task_id: UUID,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    duration_min: int | None = None,
    llm_value: float | None = None,
    requirement: str | None = None,
) -> Task:
    """Update fields of an existing task.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to update.
        title: New task title (1-500 characters).
        description: New task description.
        status: New status ('pending', 'in_progress', 'completed', 'cancelled').
        duration_min: New estimated duration in minutes (>= 1).
        llm_value: New value score (0-100 scale).
        requirement: New requirement/conclusion (1-500 characters).

    Returns:
        Updated Task object.

    Raises:
        ModelRetry: If validation fails or task not found.
    """
    try:
        task_status = TaskStatus(status) if status else None
        task_data = TaskUpdate(
            title=title,
            description=description,
            status=task_status,
            duration_min=duration_min,
            llm_value=llm_value,
            requirement=requirement,
        )
        return ctx.deps.task_repo.update_task(task_id, task_data)
    except (ValidationError, ValueError, TaskNotFoundError) as e:
        raise ModelRetry(str(e)) from e


def list_tasks_tool(  # noqa: PLR0913
    ctx: RunContext[TaskDependencies],
    status: str | None = None,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "priority",
    response_format: str = "concise",
) -> str | dict:
    r"""List tasks with pagination and flexible output format.

    Returns up to `limit` tasks to avoid overwhelming context window.
    Use response_format='concise' for token-efficient summaries,
    'detailed' for full Task objects when chaining tools.

    Args:
        ctx: Runtime context containing TaskDependencies.
        status: Optional filter (pending, in_progress, completed, cancelled).
        limit: Maximum tasks to return (default 10, max 50).
        offset: Number of tasks to skip for pagination.
        sort_by: Sort order: priority (default), created_at, duration_min.
        response_format: Output format: concise (default) or detailed.

    Returns:
        If concise: Human-readable summary string.
        If detailed: Dict with tasks, total_count, has_more, suggestion.

    Raises:
        ModelRetry: If sort_by or response_format is invalid.

    Example:
        >>> list_tasks_tool(ctx, status="pending", limit=5)
        "Found 12 tasks:\\n1. Build login (Status: pending, Priority: 2.5)..."
    """
    # Validate response_format
    try:
        fmt = ResponseFormat(response_format)
    except ValueError:
        raise ModelRetry(f"Invalid response_format: {response_format}. Use: concise, detailed") from None

    # Validate and convert status
    task_status = TaskStatus(status) if status else None
    all_tasks = ctx.deps.task_repo.list_tasks(status=task_status)

    # Sort based on sort_by parameter
    if sort_by == "priority":
        all_tasks.sort(key=lambda t: t.priority, reverse=True)
    elif sort_by == "created_at":
        all_tasks.sort(key=lambda t: t.created_at, reverse=True)
    elif sort_by == "duration_min":
        all_tasks.sort(key=lambda t: t.duration_min)
    else:
        raise ModelRetry(f"Invalid sort_by: {sort_by}. Use: priority, created_at, duration_min") from None

    # Enforce max limit and paginate
    effective_limit = min(limit, 50)
    paginated = all_tasks[offset : offset + effective_limit]
    total_count = len(all_tasks)
    has_more = (offset + len(paginated)) < total_count

    # Format based on response_format
    if fmt == ResponseFormat.CONCISE:
        if not paginated:
            status_str = f" with status '{status}'" if status else ""
            return f"No tasks found{status_str}."

        lines = [f"Found {total_count} task{'s' if total_count != 1 else ''}:\n"]
        for i, task in enumerate(paginated, start=offset + 1):
            lines.append(_format_task_concise(task, i))

        if has_more:
            remaining = total_count - (offset + len(paginated))
            lines.append(f"\n... {remaining} more (use offset={offset + effective_limit})")

        return "\n".join(lines)

    # Detailed format
    result: dict = {
        "tasks": paginated,
        "total_count": total_count,
        "has_more": has_more,
    }
    if has_more:
        remaining = total_count - (offset + len(paginated))
        result["suggestion"] = (
            f"Showing {len(paginated)} of {total_count}. Use offset={offset + effective_limit} for next page."
        )
    return result


def search_tasks_tool(  # noqa: PLR0913
    ctx: RunContext[TaskDependencies],
    query: str,
    status: str | None = None,
    min_priority: float | None = None,
    max_duration: int | None = None,
    limit: int = 10,
    response_format: str = "concise",
) -> str | dict:
    r"""Search tasks by keyword with optional filters.

    Searches across title, description, and requirement fields.
    More token-efficient than list_tasks_tool when looking for specific tasks.

    Args:
        ctx: Runtime context containing TaskDependencies.
        query: Keyword to search (case-insensitive, partial match).
        status: Optional status filter.
        min_priority: Only tasks with priority >= this value.
        max_duration: Only tasks with duration_min <= this value.
        limit: Maximum results (default 10, max 50).
        response_format: concise (default) or detailed.

    Returns:
        If concise: Human-readable string with matching tasks.
        If detailed: Dict with tasks, total_matches, query.

    Raises:
        ModelRetry: If query empty or response_format invalid.

    Example:
        >>> search_tasks_tool(ctx, "login", status="pending")
        "Found 3 matches for 'login':\\n1. Build login (Priority: 2.5)..."
    """
    # Validate query
    if not query or not query.strip():
        raise ModelRetry("Search query cannot be empty.") from None

    # Validate response_format
    try:
        fmt = ResponseFormat(response_format)
    except ValueError:
        raise ModelRetry(f"Invalid response_format: {response_format}. Use: concise, detailed") from None

    # Get base task list
    task_status = TaskStatus(status) if status else None
    all_tasks = ctx.deps.task_repo.list_tasks(status=task_status)

    # Filter by keyword (case-insensitive)
    query_lower = query.strip().lower()
    matching = [
        t
        for t in all_tasks
        if query_lower in t.title.lower()
        or (t.description and query_lower in t.description.lower())
        or query_lower in t.requirement.lower()
    ]

    # Apply additional filters
    if min_priority is not None:
        matching = [t for t in matching if t.priority >= min_priority]
    if max_duration is not None:
        matching = [t for t in matching if t.duration_min <= max_duration]

    # Sort by priority and paginate
    matching.sort(key=lambda t: t.priority, reverse=True)
    effective_limit = min(limit, 50)
    paginated = matching[:effective_limit]
    total_matches = len(matching)
    has_more = len(matching) > len(paginated)

    # Format response
    if fmt == ResponseFormat.CONCISE:
        if not paginated:
            return f"No tasks found matching '{query}'."

        lines = [f"Found {total_matches} match{'es' if total_matches != 1 else ''} for '{query}':\n"]
        for i, task in enumerate(paginated, start=1):
            lines.append(_format_task_concise(task, i))

        if has_more:
            remaining = total_matches - len(paginated)
            lines.append(f"\n... {remaining} more matches")

        return "\n".join(lines)

    # Detailed format
    result: dict = {
        "tasks": paginated,
        "total_matches": total_matches,
        "query": query,
    }
    if has_more:
        result["suggestion"] = f"Showing {len(paginated)} of {total_matches} matches."
    return result


def mark_task_completed_tool(
    ctx: RunContext[TaskDependencies],
    task_id: UUID,
    duration_actual: int | None = None,
    conclusion: str | None = None,
) -> str:
    """Mark a task as completed and optionally record completion data for pattern learning.

    Transitions task to completed status and unblocks any tasks depending on it.
    If duration_actual is provided, creates a completion record with variance tracking.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to mark as completed.
        duration_actual: Optional. Actual time spent in minutes. Enables completion tracking.
        conclusion: Optional. What was learned or delivered. Captures insights for future tasks.

    Returns:
        Confirmation message with task title and variance information if tracked.

    Raises:
        ModelRetry: If task doesn't exist. LLM can retry with correct task ID.

    Example:
        >>> mark_task_completed_tool(ctx, UUID("..."))
        "✅ Task 'Build login feature' marked as completed"

        >>> mark_task_completed_tool(ctx, UUID("..."), duration_actual=90, conclusion="OAuth2 setup")
        "✅ Completed 'Build login feature' (60min estimated, 90min actual, +50.0% variance)"
    """
    try:
        task = ctx.deps.task_repo.mark_completed(task_id)

        # If duration provided, record completion for pattern learning
        if duration_actual is not None:
            completion = ctx.deps.completion_repo.create_completion(
                CompletionCreate(
                    task_id=task_id,
                    status=CompletionStatus.COMPLETED,
                    duration_expected=task.duration_min,  # Immutable snapshot
                    duration_actual=duration_actual,
                    conclusion=conclusion,
                )
            )

            variance_sign = "+" if completion.variance_minutes > 0 else ""
            return (
                f"✅ Completed '{task.title}' "
                f"({completion.duration_expected}min estimated, {completion.duration_actual}min actual, "
                f"{variance_sign}{completion.variance_percent:.1f}% variance)"
            )

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


def mark_task_cancelled_tool(
    ctx: RunContext[TaskDependencies],
    task_id: UUID,
    duration_actual: int | None = None,
    conclusion: str | None = None,
) -> str:
    """Mark a task as cancelled and optionally record why for learning.

    Transitions task to cancelled status to remove from active workload.
    If duration_actual is provided, records time spent before cancellation.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to mark as cancelled.
        duration_actual: Optional. Time spent before cancellation in minutes.
        conclusion: Optional. Why task was cancelled. Helps avoid similar tasks.

    Returns:
        Confirmation message with task title and cancellation details if tracked.

    Raises:
        ModelRetry: If task doesn't exist. LLM can retry with correct task ID.

    Example:
        >>> mark_task_cancelled_tool(ctx, UUID("..."))
        "❌ Task 'Build login feature' marked as cancelled"

        >>> mark_task_cancelled_tool(ctx, UUID("..."), duration_actual=30, conclusion="Requirements changed")
        "❌ Cancelled 'Build login feature' (spent 30min)"
    """
    try:
        task = ctx.deps.task_repo.mark_cancelled(task_id)

        # If duration provided, record cancellation for pattern learning
        if duration_actual is not None:
            ctx.deps.completion_repo.create_completion(
                CompletionCreate(
                    task_id=task_id,
                    status=CompletionStatus.CANCELLED,
                    duration_expected=task.duration_min,  # Immutable snapshot
                    duration_actual=duration_actual,
                    conclusion=conclusion,
                )
            )

            return f"❌ Cancelled '{task.title}' (spent {duration_actual}min)"

        return f"❌ Task '{task.title}' marked as cancelled"
    except TaskNotFoundError as e:
        raise ModelRetry(str(e)) from e


def update_task_status_tool(
    ctx: RunContext[TaskDependencies],
    task_id: UUID,
    new_status: str,
    duration_actual: int | None = None,
    conclusion: str | None = None,
) -> str:
    """Update task status with optional completion tracking.

    Transitions tasks through workflow states:
    - pending -> in_progress: Start working
    - in_progress -> completed: Finish with optional time tracking
    - any -> cancelled: Abandon with optional reason

    Replaces separate mark_task_completed, mark_task_in_progress,
    and mark_task_cancelled tools.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of task to update.
        new_status: Target status (in_progress, completed, cancelled).
        duration_actual: Actual time in minutes (for completed/cancelled).
        conclusion: Notes or reason (for completed/cancelled).

    Returns:
        Confirmation message with status details.

    Raises:
        ModelRetry: If task not found or new_status invalid.

    Example:
        >>> update_task_status_tool(ctx, task_id, "in_progress")
        "Task 'Build login' marked as in progress"
        >>> update_task_status_tool(ctx, task_id, "completed", duration_actual=90)
        "Completed 'Build login' (120min estimated, 90min actual, -25.0% variance)"
    """
    valid_statuses = ["in_progress", "completed", "cancelled"]
    if new_status not in valid_statuses:
        raise ModelRetry(f"Invalid new_status: {new_status}. Use: {', '.join(valid_statuses)}") from None

    try:
        new_status_enum = TaskStatus(new_status)

        if new_status_enum == TaskStatus.COMPLETED:
            task = ctx.deps.task_repo.mark_completed(task_id)
            if duration_actual is not None:
                completion = ctx.deps.completion_repo.create_completion(
                    CompletionCreate(
                        task_id=task_id,
                        status=CompletionStatus.COMPLETED,
                        duration_expected=task.duration_min,
                        duration_actual=duration_actual,
                        conclusion=conclusion,
                    )
                )
                sign = "+" if completion.variance_minutes > 0 else ""
                return (
                    f"✅ Completed '{task.title}' "
                    f"({completion.duration_expected}min estimated, "
                    f"{completion.duration_actual}min actual, "
                    f"{sign}{completion.variance_percent:.1f}% variance)"
                )
            return f"✅ Task '{task.title}' marked as completed"

        if new_status_enum == TaskStatus.IN_PROGRESS:
            task = ctx.deps.task_repo.mark_in_progress(task_id)
            return f"🚀 Task '{task.title}' marked as in progress"

        if new_status_enum == TaskStatus.CANCELLED:
            task = ctx.deps.task_repo.mark_cancelled(task_id)
            if duration_actual is not None:
                ctx.deps.completion_repo.create_completion(
                    CompletionCreate(
                        task_id=task_id,
                        status=CompletionStatus.CANCELLED,
                        duration_expected=task.duration_min,
                        duration_actual=duration_actual,
                        conclusion=conclusion,
                    )
                )
                return f"❌ Cancelled '{task.title}' (spent {duration_actual}min)"
            return f"❌ Task '{task.title}' cancelled"

        # Unreachable - all valid statuses handled above
        msg = f"Unexpected status: {new_status_enum}"
        raise RuntimeError(msg)

    except TaskNotFoundError as e:
        raise ModelRetry(
            f"Task {task_id} not found. Use list_tasks_tool(response_format='detailed') to find task IDs."
        ) from e


def get_task_details_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> Task:
    """Get detailed information about a specific task.

    Retrieves full task metadata for inspection or tool chaining.
    Use when you need complete task data before updating.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to retrieve.

    Returns:
        Task object with all fields.

    Raises:
        ModelRetry: If task not found. Use list_tasks_tool to find valid IDs.

    Example:
        >>> task = get_task_details_tool(ctx, UUID("..."))
        >>> print(f"{task.title}: {task.requirement}")
    """
    task: Task | None = ctx.deps.task_repo.get_task(task_id)

    if task is None:
        raise ModelRetry(
            f"Task {task_id} not found. Use list_tasks_tool(response_format='detailed') to see available task IDs."
        ) from None

    return task


def list_open_tasks_full(ctx: RunContext[TaskDependencies]) -> list[TaskWithPriority]:
    """List open tasks with dependency counts and effective priorities.

    Returns tasks enriched with:
    - Dependency counts (tasks_blocked_count, active_blocker_count)
    - Effective priority (considering DAG inheritance)

    Args:
        ctx: Runtime context containing TaskDependencies.

    Returns:
        List of TaskWithPriority objects.
    """
    return ctx.deps.dep_repo.list_tasks_with_priority()


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
