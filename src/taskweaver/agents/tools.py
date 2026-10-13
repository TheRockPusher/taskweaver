"""Agent tools for task management operations.

This module defines PydanticAI tools that wrap TaskRepository methods,
providing a clean interface for the orchestrator agent to interact with tasks.

Error Handling Strategy:
- ModelRetry: Raised when tool fails due to invalid input that LLM can fix
    (circular dependencies, invalid task IDs, validation errors)
- The LLM receives the error message and can retry with corrected parameters
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from taskweaver.database.exceptions import DependencyError, TaskNotFoundError
from taskweaver.database.models import (
    CompletionStatus,
    TaskDependency,
    TaskWithPriority,
)

from ..database.models import Task, TaskCreate, TaskStatus, TaskUpdate
from ..database.planning import PlanningService
from ..database.priority_service import PriorityService, PriorityWeights
from .calculator import evaluate_expression
from .dependencies import TaskDependencies
from .memory import MemoryFact, MemoryService

# Display constants
MAX_TITLE_LENGTH = 60


def require_write_access(ctx: RunContext[TaskDependencies]) -> None:
    """Reject review mutations before opening services or touching repositories."""
    if ctx.deps.request_mode == "review":
        raise ModelRetry("Review is read-only; this operation is not authorized.")


class ResponseFormat(str, Enum):
    """Output format for tool results."""

    CONCISE = "concise"  # Human-readable summary (token-efficient)
    DETAILED = "detailed"  # Full structured data (for tool chaining)


def _format_task_concise(task: Task, index: int = 0) -> str:
    """Summarize working duration, enum status and separate CD3 value/time."""
    idx_str = f"{index}. " if index > 0 else ""
    return (
        f"{idx_str}{task.title[:MAX_TITLE_LENGTH]} "
        f"(Status: {task.status.value}, Priority: {task.priority:.2f}, "
        f"Duration: {task.duration_min}min)"
    )


def create_task_tool(  # noqa: PLR0913
    ctx: RunContext[TaskDependencies],
    title: str,
    duration_min: int,
    llm_value: float,
    requirement: str,
    description: str | None = None,
    urgency: int = 3,
    importance: int = 3,
    effort: int = 3,
    category: str = "general",
    goal_id: UUID | None = None,
    skill_domain: str | None = None,
    required_skill_level: int | None = None,
) -> dict:
    """Create work with MCDA factors, goal and skill requirements; learn category duration once."""
    require_write_access(ctx)
    with _tool_errors():
        _require_goal(ctx, goal_id)
        task = ctx.deps.task_repo.create_task(
            TaskCreate(
                title=title,
                description=description,
                duration_min=duration_min,
                llm_value=llm_value,
                requirement=requirement,
                urgency=urgency,
                importance=importance,
                effort=effort,
                category=category,
                goal_id=goal_id,
                skill_domain=skill_domain,
                required_skill_level=required_skill_level,
            ),
        )
        return task.model_dump(mode="json")


def update_task_tool(
    ctx: RunContext[TaskDependencies],
    task_id: UUID,
    changes: TaskUpdate | dict[str, object],
) -> Task:
    """Apply supplied fields only. Omit nullable fields to keep them; explicit null clears them."""
    require_write_access(ctx)
    with _tool_errors():
        updates = TaskUpdate.model_validate(changes)
        _require_goal(ctx, updates.goal_id)
        return ctx.deps.task_repo.update_task(task_id, updates)


def list_tasks_tool(  # noqa: PLR0913
    ctx: RunContext[TaskDependencies],
    status: str | None = None,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "priority",
    response_format: str = "concise",
) -> str | dict:
    """List tasks: up to 50 per page; concise summaries or detailed JSON.

    Sort by CD3 priority, MCDA score, created_at or duration_min.
    """
    fmt = _response_format(response_format)

    # Validate and convert status
    task_status = _task_status(status)
    _validate_page(limit, offset)
    all_tasks = ctx.deps.task_repo.list_tasks(status=task_status)

    # Sort based on sort_by parameter
    if sort_by == "priority":
        all_tasks.sort(key=lambda t: t.priority, reverse=True)
    elif sort_by == "score":
        all_tasks.sort(key=lambda t: t.priority_score or 0.0, reverse=True)
    elif sort_by == "created_at":
        all_tasks.sort(key=lambda t: t.created_at, reverse=True)
    elif sort_by == "duration_min":
        all_tasks.sort(key=lambda t: t.duration_min)
    else:
        raise ModelRetry(f"Invalid sort_by: {sort_by}. Use: priority, score, created_at, duration_min") from None

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

        lines = _concise_tasks(paginated, f"Found {total_count} task{'s' if total_count != 1 else ''}:", offset)

        if has_more:
            remaining = total_count - (offset + len(paginated))
            lines.append(f"\n... {remaining} more (use offset={offset + effective_limit})")

        return "\n".join(lines)

    # Detailed format
    result: dict = {
        "tasks": [task.model_dump(mode="json") for task in paginated],
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
    """Search title, description and requirement; optional CD3/duration/status filters, max 50 results."""
    # Validate query
    if not query or not query.strip():
        raise ModelRetry("Search query cannot be empty.") from None

    fmt = _response_format(response_format)

    # Get base task list
    task_status = _task_status(status)
    _validate_page(limit)
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

        lines = _concise_tasks(
            paginated,
            f"Found {total_matches} match{'es' if total_matches != 1 else ''} for '{query}':",
        )

        if has_more:
            remaining = total_matches - len(paginated)
            lines.append(f"\n... {remaining} more matches")

        return "\n".join(lines)

    # Detailed format
    result: dict = {
        "tasks": [task.model_dump(mode="json") for task in paginated],
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
    """Complete work; measured actual time records an atomic immutable snapshot before blocker cleanup."""
    require_write_access(ctx)
    try:
        if duration_actual is not None:
            task = get_task_details_tool(ctx, task_id)
            completion = ctx.deps.completion_repo.complete_task(
                task_id,
                actual_minutes=duration_actual,
                conclusion=conclusion,
            )

            variance_sign = "+" if completion.variance_minutes > 0 else ""
            return (
                f"✅ Completed '{task.title}' "
                f"({completion.duration_expected}min estimated, {completion.duration_actual}min actual, "
                f"{variance_sign}{completion.variance_percent:.1f}% variance)"
            )
        task = ctx.deps.task_repo.mark_completed(task_id)

        return f"✅ Task '{task.title}' marked as completed"
    except (TaskNotFoundError, ValueError) as e:
        raise ModelRetry(str(e)) from e


def mark_task_cancelled_tool(
    ctx: RunContext[TaskDependencies],
    task_id: UUID,
    duration_actual: int | None = None,
    conclusion: str | None = None,
) -> str:
    """Cancel work; optional measured actual time records evidence, never invent time from conclusions."""
    require_write_access(ctx)
    try:
        if duration_actual is not None:
            task = get_task_details_tool(ctx, task_id)
            ctx.deps.completion_repo.complete_task(
                task_id,
                actual_minutes=duration_actual,
                conclusion=conclusion,
                status=CompletionStatus.CANCELLED,
            )

            return f"❌ Cancelled '{task.title}' (spent {duration_actual}min)"
        task = ctx.deps.task_repo.mark_cancelled(task_id)

        return f"❌ Task '{task.title}' marked as cancelled"
    except (TaskNotFoundError, ValueError) as e:
        raise ModelRetry(str(e)) from e


def update_task_status_tool(
    ctx: RunContext[TaskDependencies],
    task_id: UUID,
    new_status: str,
    duration_actual: int | None = None,
    conclusion: str | None = None,
) -> str:
    """Start, complete or cancel work; only measured closure time creates completion evidence."""
    require_write_access(ctx)
    valid_statuses = ["in_progress", "completed", "cancelled"]
    if new_status not in valid_statuses:
        raise ModelRetry(f"Invalid new_status: {new_status}. Use: {', '.join(valid_statuses)}") from None

    try:
        new_status_enum = TaskStatus(new_status)

        if new_status_enum == TaskStatus.COMPLETED:
            return mark_task_completed_tool(ctx, task_id, duration_actual, conclusion)

        if new_status_enum == TaskStatus.IN_PROGRESS:
            task = ctx.deps.task_repo.mark_in_progress(task_id)
            return f"🚀 Task '{task.title}' marked as in progress"

        return mark_task_cancelled_tool(ctx, task_id, duration_actual, conclusion)

    except TaskNotFoundError as e:
        raise ModelRetry(
            f"Task {task_id} not found. Use list_tasks_tool(response_format='detailed') to find task IDs."
        ) from e


def get_task_details_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> Task:
    """Read full task metadata; missing task IDs produce a correctable error."""
    task: Task | None = ctx.deps.task_repo.get_task(task_id)

    if task is None:
        raise ModelRetry(
            f"Task {task_id} not found. Use list_tasks_tool(response_format='detailed') to see available task IDs."
        ) from None

    return task


def list_open_tasks_full(ctx: RunContext[TaskDependencies]) -> list[TaskWithPriority]:
    """List active tasks with dependency counts and inherited CD3 value/time (not MCDA score)."""
    return ctx.deps.dep_repo.list_tasks_with_priority()


def add_dependency_tool(ctx: RunContext[TaskDependencies], task_id: UUID, blocker_id: UUID) -> TaskDependency:
    """Make task_id wait for blocker_id; reject cycles, duplicates and closed endpoints."""
    require_write_access(ctx)
    try:
        return ctx.deps.dep_repo.add_dependency(task_id, blocker_id)
    except (DependencyError, TaskNotFoundError) as e:
        raise ModelRetry(str(e)) from e


def get_blockers_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> list[Task]:
    """Read active blockers; missing task IDs produce a correctable error."""
    with _tool_errors():
        get_task_details_tool(ctx, task_id)
        return ctx.deps.dep_repo.get_blockers(task_id)


def get_blocked_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> list[Task]:
    """Read tasks waiting on this task; missing task IDs produce a correctable error."""
    with _tool_errors():
        get_task_details_tool(ctx, task_id)
        return ctx.deps.dep_repo.get_blocked(task_id)


def remove_dependency_tool(ctx: RunContext[TaskDependencies], task_id: UUID, blocker_id: UUID) -> str:
    """Remove an existing blocker edge without altering either task."""
    require_write_access(ctx)
    try:
        ctx.deps.dep_repo.remove_dependency(task_id, blocker_id)
        return f"✅ Dependency removed: {task_id} no longer blocked by {blocker_id}"
    except (DependencyError, TaskNotFoundError) as e:
        raise ModelRetry(str(e)) from e


def calculator_tool(
    ctx: RunContext[TaskDependencies],  # noqa: ARG001
    expression: str,
) -> str:
    """Evaluate bounded numeric arithmetic for priorities and duration analysis.

    Args:
        ctx: Task repositories (unused for this stateless operation).
        expression: Numbers, arithmetic operators, and parentheses.

    Returns:
        Expression and numeric result; floats use four decimal places.

    Raises:
        ModelRetry: If the expression is invalid, unsafe, or divides by zero.
    """
    try:
        return evaluate_expression(expression)
    except ZeroDivisionError as error:
        raise ModelRetry("Division by zero. Check the denominator.") from error
    except ValueError as error:
        raise ModelRetry(f"Invalid mathematical expression: {error}") from error


@contextmanager
def _tool_errors() -> Iterator[None]:
    """Translate correctable inputs, not database or programming failures."""
    try:
        yield
    except (ValidationError, ValueError, TaskNotFoundError, DependencyError) as error:
        raise ModelRetry(str(error)) from error


def _planning(ctx: RunContext[TaskDependencies]) -> PlanningService:
    if ctx.deps.planning is None:
        ctx.deps.planning = PlanningService(ctx.deps.task_repo.db_path)
    return ctx.deps.planning


def _memory(ctx: RunContext[TaskDependencies]) -> MemoryService:
    if ctx.deps.memory is None:
        ctx.deps.memory = MemoryService(ctx.deps.task_repo.db_path, user_id=ctx.deps.user_id)
    return ctx.deps.memory


def _priority(ctx: RunContext[TaskDependencies]) -> PriorityService:
    return PriorityService(ctx.deps.task_repo.db_path)


def _task_status(status: str | None) -> TaskStatus | None:
    with _tool_errors():
        return TaskStatus(status) if status is not None else None


def _validate_page(limit: int, offset: int = 0) -> None:
    if limit < 1 or offset < 0:
        raise ModelRetry("Limit must be positive and offset must be nonnegative")


def _require_goal(ctx: RunContext[TaskDependencies], goal_id: UUID | None) -> None:
    if goal_id is not None and _planning(ctx).get_goal(goal_id) is None:
        raise ModelRetry(f"Goal not found: {goal_id}")


def score_task_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> dict:
    """Persist current MCDA score and return exact contributions, inherited score and trend."""
    require_write_access(ctx)
    with _tool_errors():
        service = _priority(ctx)
        service.update_task_priority(task_id)
        return {**service.explain(task_id), "trend": service.trend(task_id), "history": service.history(task_id)}


def recalculate_priorities_tool(ctx: RunContext[TaskDependencies], status: str | None = None) -> dict:
    """Refresh changed MCDA scores; omit status for active work only."""
    require_write_access(ctx)
    with _tool_errors():
        service = _priority(ctx)
        selected = _task_status(status)
        changed = service.update_all_priorities(selected)
        scores = service.calculate_all_priorities(selected)
        return {"changed": changed, "scores": {str(task_id): score for task_id, score in scores.items()}}


def rank_tasks_tool(ctx: RunContext[TaskDependencies], limit: int = 10, match_skills: bool = True) -> list[dict]:
    """Rank actionable work by inherited MCDA score; exclude blockers and optionally skill gaps."""
    with _tool_errors():
        return [task.model_dump(mode="json") for task in _priority(ctx).get_top_priorities(limit, match_skills)]


def priority_weights_tool(ctx: RunContext[TaskDependencies], weights: PriorityWeights | None = None) -> dict:
    """Show current weights, or explicitly replace all five finite weights summing to one."""
    if weights is not None:
        require_write_access(ctx)
    with _tool_errors():
        service = _priority(ctx)
        if weights is not None:
            service.adjust_weights(PriorityWeights.model_validate(weights))
        return service.weights.model_dump(mode="json")


def create_goal_tool(ctx: RunContext[TaskDependencies], title: str, description: str | None = None) -> dict:
    """Create an outcome without silently creating tasks."""
    require_write_access(ctx)
    with _tool_errors():
        return _planning(ctx).create_goal(title, description).model_dump(mode="json")


def list_goals_tool(ctx: RunContext[TaskDependencies]) -> list[dict]:
    """List outcomes together with completed/noncancelled task progress."""
    with _tool_errors():
        service = _planning(ctx)
        return [service.goal_progress(goal.goal_id).model_dump(mode="json") for goal in service.list_goals()]


def goal_progress_tool(ctx: RunContext[TaskDependencies], goal_id: UUID) -> dict:
    """Report completed fraction, linked total and cancellations; empty progress is zero."""
    with _tool_errors():
        return _planning(ctx).goal_progress(goal_id).model_dump(mode="json")


def update_goal_tool(
    ctx: RunContext[TaskDependencies],
    goal_id: UUID,
    title: str | None = None,
    description: str | None = None,
    replace_description: bool = False,
) -> dict:
    """Edit a goal; set replace_description to clear with null, otherwise omitted description is kept."""
    require_write_access(ctx)
    with _tool_errors():
        service = _planning(ctx)
        goal = service.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")
        new_description = description if description is not None or replace_description else goal.description
        return service.update_goal(goal_id, title, new_description).model_dump(mode="json")


def delete_goal_tool(ctx: RunContext[TaskDependencies], goal_id: UUID) -> dict:
    """Delete an outcome and unlink its tasks without deleting work."""
    require_write_access(ctx)
    with _tool_errors():
        _planning(ctx).delete_goal(goal_id)
        return {"deleted_goal_id": str(goal_id)}


def link_task_goal_tool(ctx: RunContext[TaskDependencies], task_id: UUID, goal_id: UUID | None) -> dict:
    """Attach work to an existing goal, or explicitly unlink it with null."""
    require_write_access(ctx)
    with _tool_errors():
        _require_goal(ctx, goal_id)
        return _planning(ctx).link_task(task_id, goal_id).model_dump(mode="json")


def assess_skill_tool(
    ctx: RunContext[TaskDependencies],
    domain: str,
    level: int,
    evidence: str,
    assessed_at: datetime | None = None,
) -> dict:
    """Record explicit evidence-backed Dreyfus level 1..5; retain history, never infer from speed."""
    require_write_access(ctx)
    with _tool_errors():
        return _planning(ctx).set_skill(domain, level, evidence, assessed_at).model_dump(mode="json")


def list_skills_tool(ctx: RunContext[TaskDependencies]) -> list[dict]:
    """Read latest observed evidence-backed assessments."""
    return [skill.model_dump(mode="json") for skill in _planning(ctx).list_skills()]


def skill_history_tool(ctx: RunContext[TaskDependencies], domain: str) -> list[dict]:
    """Read chronological evidence including backfills, corrections and regressions."""
    if not domain.strip():
        raise ModelRetry("Skill domain must not be empty")
    return [skill.model_dump(mode="json") for skill in _planning(ctx).skill_history(domain)]


def match_task_skills_tool(ctx: RunContext[TaskDependencies], task_id: UUID) -> dict:
    """Explain readiness, blockers and unknown or insufficient skill levels for one task."""
    with _tool_errors():
        return _planning(ctx).match(task_id).model_dump(mode="json")


def recommendations_tool(ctx: RunContext[TaskDependencies]) -> dict:
    """Separate actionable work from learning gaps; blocked work is never recommended."""
    return _planning(ctx).recommendations().model_dump(mode="json")


def work_analysis_tool(ctx: RunContext[TaskDependencies], max_minutes: int = 30, limit: int = 5) -> dict:
    """Read duration critical path and skill/dependency-ready CD3 quick wins.

    Assumes unlimited parallel capacity, excludes learning time, and predicts no dates.
    """
    with _tool_errors():
        return _planning(ctx).work_analysis(max_minutes, limit).model_dump(mode="json")


def estimate_duration_tool(ctx: RunContext[TaskDependencies], category: str, baseline_minutes: int) -> dict:
    """Apply category evidence once to a raw estimate; expose count, median and dispersion."""
    with _tool_errors():
        if not category.strip():
            raise ValueError("Category must not be empty")
        return _planning(ctx).estimate(category, baseline_minutes).model_dump(mode="json")


def completion_insights_tool(ctx: RunContext[TaskDependencies]) -> list[dict]:
    """Read immutable category completion/cancellation evidence and duration confidence."""
    return [insight.model_dump(mode="json") for insight in _planning(ctx).insights()]


_FACT_ADAPTER = TypeAdapter(MemoryFact)


def remember_fact_tool(
    ctx: RunContext[TaskDependencies],
    key: str,
    value: str,
    category: str = "preference",
    expires_at: datetime | None = None,
) -> dict:
    """Store only an explicitly requested user fact locally; optional injected semantic backend mirrors it."""
    require_write_access(ctx)
    with _tool_errors():
        return _FACT_ADAPTER.dump_python(_memory(ctx).remember(key, value, category, expires_at), mode="json")


def update_fact_tool(
    ctx: RunContext[TaskDependencies],
    key: str,
    value: str,
    category: str = "preference",
    expires_at: datetime | None = None,
) -> dict:
    """Explicitly correct a fact; obsolete semantic versions cannot resurface."""
    require_write_access(ctx)
    with _tool_errors():
        return _FACT_ADAPTER.dump_python(_memory(ctx).update(key, value, category, expires_at), mode="json")


def forget_fact_tool(ctx: RunContext[TaskDependencies], key: str) -> dict:
    """Remove a user fact authoritatively before attempting optional backend deletion."""
    require_write_access(ctx)
    with _tool_errors():
        return {"forgotten": _memory(ctx).forget(key)}


def list_facts_tool(ctx: RunContext[TaskDependencies], category: str | None = None) -> list[dict]:
    """List current unexpired facts for this user only."""
    with _tool_errors():
        if category is not None and category not in ("preference", "skill", "goal", "context"):
            raise ValueError("Unsupported memory category")
        return [_FACT_ADAPTER.dump_python(fact, mode="json") for fact in _memory(ctx).list_facts(category)]


def search_facts_tool(ctx: RunContext[TaskDependencies], query: str, limit: int = 10) -> list[dict]:
    """Retrieve user facts, filtering forgotten, expired and replaced versions."""
    with _tool_errors():
        if not query.strip():
            raise ValueError("Memory query must not be empty")
        _validate_page(limit)
        return [_FACT_ADAPTER.dump_python(fact, mode="json") for fact in _memory(ctx).search(query, limit)]


def _response_format(value: str) -> ResponseFormat:
    try:
        return ResponseFormat(value)
    except ValueError as error:
        raise ModelRetry(f"Invalid response_format: {value}. Use: concise, detailed") from error


def _concise_tasks(tasks: list[Task], heading: str, offset: int = 0) -> list[str]:
    return [heading + "\n", *(_format_task_concise(task, index) for index, task in enumerate(tasks, offset + 1))]
