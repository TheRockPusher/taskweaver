"""Agent tools for task management operations.

This module defines PydanticAI tools that wrap TaskRepository methods,
providing a clean interface for the orchestrator agent to interact with tasks.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic_ai import RunContext

from ..database.models import TaskCreate, TaskStatus

if TYPE_CHECKING:
    from .task_agent import TaskDependencies

# Display constants
MAX_TITLE_LENGTH = 60
MAX_DESCRIPTION_LENGTH = 40


def create_task_tool(ctx: "RunContext[TaskDependencies]", title: str, description: str | None = None) -> str:
    """Create a new task.

    Args:
        ctx: Runtime context containing TaskDependencies.
        title: Task title (1-500 characters).
        description: Optional task description.

    Returns:
        Success message with task ID and title.

    Example:
        >>> create_task_tool(ctx, "Build login feature", "Implement OAuth2")
        "✅ Created task 'Build login feature' (ID: 123e4567-...)"
    """
    task_data = TaskCreate(title=title, description=description)
    task = ctx.deps.task_repo.create_task(task_data)
    return f"✅ Created task '{task.title}' (ID: {task.task_id})"


def list_tasks_tool(ctx: "RunContext[TaskDependencies]", status: str | None = None) -> str:
    r"""List all tasks or filter by status.

    Args:
        ctx: Runtime context containing TaskDependencies.
        status: Optional status filter. Valid values: 'pending', 'in_progress', 'completed', 'cancelled'.

    Returns:
        Formatted list of tasks with IDs, titles, and statuses.

    Example:
        >>> list_tasks_tool(ctx, status="pending")
        "3 task(s):\n• 123e4567: Build login feature [pending]\n..."
    """
    # Parse status string to enum if provided
    task_status = TaskStatus(status) if status else None

    tasks = ctx.deps.task_repo.list_tasks(status=task_status)

    if not tasks:
        filter_msg = f" with status '{status}'" if status else ""
        return f"No tasks found{filter_msg}."

    # Format task list
    status_msg = f" [{status}]" if status else ""
    lines = [f"📋 {len(tasks)} task(s){status_msg}:\n"]

    for task in tasks:
        # Truncate long titles for readability
        title = task.title[:MAX_TITLE_LENGTH] + "..." if len(task.title) > MAX_TITLE_LENGTH else task.title
        desc_preview = ""
        if task.description:
            desc_preview = (
                f" - {task.description[:MAX_DESCRIPTION_LENGTH]}..."
                if len(task.description) > MAX_DESCRIPTION_LENGTH
                else f" - {task.description}"
            )

        lines.append(f"• {task.task_id}: {title} [{task.status}]{desc_preview}")

    return "\n".join(lines)


def mark_task_completed_tool(ctx: "RunContext[TaskDependencies]", task_id: str) -> str:
    """Mark a task as completed.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to mark as completed.

    Returns:
        Success message with task title.

    Raises:
        TaskNotFoundError: If task doesn't exist.

    Example:
        >>> mark_task_completed_tool(ctx, "123e4567-e89b-12d3-a456-426614174000")
        "✅ Task 'Build login feature' marked as completed"
    """
    task_uuid = UUID(task_id)
    task = ctx.deps.task_repo.mark_completed(task_uuid)
    return f"✅ Task '{task.title}' marked as completed"


def mark_task_in_progress_tool(ctx: "RunContext[TaskDependencies]", task_id: str) -> str:
    """Mark a task as in progress.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to mark as in progress.

    Returns:
        Success message with task title.

    Raises:
        TaskNotFoundError: If task doesn't exist.

    Example:
        >>> mark_task_in_progress_tool(ctx, "123e4567-e89b-12d3-a456-426614174000")
        "🚀 Task 'Build login feature' marked as in progress"
    """
    task_uuid = UUID(task_id)
    task = ctx.deps.task_repo.mark_in_progress(task_uuid)
    return f"🚀 Task '{task.title}' marked as in progress"


def mark_task_cancelled_tool(ctx: "RunContext[TaskDependencies]", task_id: str) -> str:
    """Mark a task as cancelled.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to mark as cancelled.

    Returns:
        Success message with task title.

    Raises:
        TaskNotFoundError: If task doesn't exist.

    Example:
        >>> mark_task_cancelled_tool(ctx, "123e4567-e89b-12d3-a456-426614174000")
        "❌ Task 'Build login feature' marked as cancelled"
    """
    task_uuid = UUID(task_id)
    task = ctx.deps.task_repo.mark_cancelled(task_uuid)
    return f"❌ Task '{task.title}' marked as cancelled"


def get_task_details_tool(ctx: "RunContext[TaskDependencies]", task_id: str) -> str:
    r"""Get detailed information about a specific task.

    Args:
        ctx: Runtime context containing TaskDependencies.
        task_id: UUID of the task to retrieve.

    Returns:
        Formatted task details including all fields.

    Raises:
        TaskNotFoundError: If task doesn't exist (returns None from repository).

    Example:
        >>> get_task_details_tool(ctx, "123e4567-e89b-12d3-a456-426614174000")
        "📋 Task Details:\nID: 123e4567...\nTitle: Build login feature\n..."
    """
    task_uuid = UUID(task_id)
    task = ctx.deps.task_repo.get_task(task_uuid)

    if task is None:
        return f"❌ Task not found: {task_id}"

    lines = [
        "📋 Task Details:",
        f"ID: {task.task_id}",
        f"Title: {task.title}",
        f"Status: {task.status.value}",
        f"Description: {task.description or '[No description]'}",
        f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Updated: {task.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]

    return "\n".join(lines)


def list_open_tasks_dep_count_tool(ctx: "RunContext[TaskDependencies]") -> str:
    r"""List open tasks sorted by dependency priority.

    Uses list_tasks_with_deps() to efficiently retrieve tasks with
    pre-calculated blocker/blocked counts from the tasks_full view.
    Prioritizes tasks with no blockers (ready to start).

    Args:
        ctx: Runtime context containing TaskDependencies.

    Returns:
        Formatted string with task list sorted by priority (ready tasks first).

    Example:
        >>> list_open_tasks_dep_count_tool(ctx)
        "📋 Open Tasks (3 total):\n✅ Ready: Task A\n🚫 Blocked by 2: Task B..."
    """
    # Get all tasks with dependency counts from tasks_full view
    all_tasks = ctx.deps.task_repo.list_tasks_with_deps()

    # Filter to only open tasks (pending or in_progress)
    open_tasks = [
        task for task in all_tasks
        if task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
    ]

    if not open_tasks:
        return "No open tasks found. All tasks are completed or cancelled."

    # Sort: tasks with no blockers first, then by how many they're blocking
    open_tasks.sort(key=lambda t: (t.active_blocker_count, -t.tasks_blocked_count))

    # Format output
    lines = [f"📋 Open Tasks ({len(open_tasks)} total):\n"]
    for idx, task in enumerate(open_tasks, 1):
        # Status icon based on blockers
        status_icon = "✅ Ready" if task.active_blocker_count == 0 else f"🚫 Blocked by {task.active_blocker_count}"

        # Additional info about blocking others
        blocking_info = f" (blocks {task.tasks_blocked_count})" if task.tasks_blocked_count > 0 else ""
        status_badge = f" [{task.status.value}]"

        lines.append(f"{idx}. {status_icon}: {task.title}{blocking_info}{status_badge}")

    return "\n".join(lines)
