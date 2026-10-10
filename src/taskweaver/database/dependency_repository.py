"""Atomic task dependencies and batched CD3 priority inheritance."""

import sqlite3
from collections import deque
from pathlib import Path
from uuid import UUID

from .connection import get_connection, get_database_path
from .exceptions import DependencyError, TaskNotFoundError
from .models import Task, TaskDependency, TaskStatus, TaskWithDependencies, TaskWithPriority
from .priority_service import refresh_priorities
from .schema import DELETE_DEPENDENCY, INSERT_DEPENDENCY, SELECT_BLOCKED_TASKS, SELECT_BLOCKERS

_ACTIVE_STATUSES = (TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value)
_ACTIVE_EDGES = """
SELECT d.task_id, d.blocker_id FROM task_dependencies d
JOIN tasks downstream ON downstream.task_id = d.task_id
JOIN tasks blocker ON blocker.task_id = d.blocker_id
WHERE downstream.status IN ('pending', 'in_progress')
AND blocker.status IN ('pending', 'in_progress')
"""


def _would_cycle(conn: sqlite3.Connection, task_id: UUID, blocker_id: UUID) -> bool:
    blockers: dict[str, list[str]] = {}
    for row in conn.execute(_ACTIVE_EDGES):
        blockers.setdefault(row["task_id"], []).append(row["blocker_id"])
    target = str(task_id)
    queue = deque([str(blocker_id)])
    visited: set[str] = set()
    while queue:
        current = queue.popleft()
        if current == target:
            return True
        if current not in visited:
            visited.add(current)
            queue.extend(blockers.get(current, ()))
    return False


def _effective_priorities(conn: sqlite3.Connection, tasks: list[TaskWithDependencies]) -> dict[UUID, float]:
    """Propagate CD3 from leaves to roots in O(tasks + edges), without recursion."""
    priorities = {task.task_id: task.priority for task in tasks}
    downstream_count = dict.fromkeys(priorities, 0)
    upstream: dict[UUID, list[UUID]] = {}
    for row in conn.execute(_ACTIVE_EDGES):
        downstream = UUID(row["task_id"])
        blocker = UUID(row["blocker_id"])
        downstream_count[blocker] += 1
        upstream.setdefault(downstream, []).append(blocker)
    queue = deque(task_id for task_id, count in downstream_count.items() if count == 0)
    processed = 0
    while queue:
        downstream = queue.popleft()
        processed += 1
        for blocker in upstream.get(downstream, ()):
            priorities[blocker] = max(priorities[blocker], priorities[downstream])
            downstream_count[blocker] -= 1
            if downstream_count[blocker] == 0:
                queue.append(blocker)
    if processed != len(priorities):
        raise DependencyError("Dependency graph contains a cycle")
    return priorities


class TaskDependencyRepository:
    """Manage active dependency edges without circular repository construction."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path if db_path is not None else get_database_path()

    def add_dependency(self, task_id: UUID, blocker_id: UUID) -> TaskDependency:
        """Create an active dependency, rejecting missing tasks, duplicates and cycles.

        Args:
            task_id: Task blocked by the dependency.
            blocker_id: Task that must finish first.

        Returns:
            Persisted dependency.

        Raises:
            TaskNotFoundError: If either endpoint does not exist.
            DependencyError: If either endpoint is terminal or the edge is invalid.
        """
        dependency = TaskDependency(task_id=task_id, blocker_id=blocker_id)
        with get_connection(self.db_path) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            for endpoint in (task_id, blocker_id):
                row = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (str(endpoint),)).fetchone()
                if row is None:
                    raise TaskNotFoundError(endpoint)
                if row["status"] not in _ACTIVE_STATUSES:
                    raise DependencyError("task is closed")
            if conn.execute(
                "SELECT 1 FROM task_dependencies WHERE task_id = ? AND blocker_id = ?",
                (str(task_id), str(blocker_id)),
            ).fetchone():
                raise DependencyError("Dependency already exists")
            if _would_cycle(conn, task_id, blocker_id):
                raise DependencyError("Dependency causes a cycle")
            conn.execute(
                INSERT_DEPENDENCY,
                (str(dependency.dependency_id), str(task_id), str(blocker_id), dependency.created_at.isoformat()),
            )
            refresh_priorities(conn)
        return dependency

    def remove_dependency(self, task_id: UUID, blocker_id: UUID) -> None:
        """Delete an existing edge and refresh rankings in the same transaction.

        Raises:
            DependencyError: If the edge does not exist.
        """
        with get_connection(self.db_path) as conn, conn:
            if not conn.execute(DELETE_DEPENDENCY, (str(task_id), str(blocker_id))).rowcount:
                raise DependencyError(f"Dependency not found: blocker-{blocker_id} -> task-{task_id}")
            refresh_priorities(conn)

    def get_blockers(self, task_id: UUID) -> list[Task]:
        """Get active blockers of an active task in one query."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(SELECT_BLOCKERS, (str(task_id),)).fetchall()
        return [Task.model_validate(dict(row)) for row in rows]

    def get_blocked(self, blocker_id: UUID) -> list[Task]:
        """Get active downstream tasks blocked by an active task in one query."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(SELECT_BLOCKED_TASKS, (str(blocker_id),)).fetchall()
        return [Task.model_validate(dict(row)) for row in rows]

    def calculate_effective_priorities(self, tasks: list[TaskWithDependencies] | None = None) -> dict[UUID, float]:
        """Calculate inherited CD3 over the complete active graph, then select tasks.

        Args:
            tasks: Optional subset to return; downstream inheritance still uses all active tasks.

        Returns:
            Effective CD3 scores keyed by task ID. MCDA scoring remains a separate metric.

        Raises:
            DependencyError: If a legacy graph contains a cycle.
        """
        with get_connection(self.db_path) as conn, conn:
            conn.execute("BEGIN")
            active = [
                TaskWithDependencies.model_validate(dict(row)) for row in conn.execute("SELECT * FROM tasks_full")
            ]
            priorities = _effective_priorities(conn, active)
        if tasks is None:
            return priorities
        return {task.task_id: priorities[task.task_id] for task in tasks if task.task_id in priorities}

    def list_tasks_with_priority(self, status: TaskStatus | None = None) -> list[TaskWithPriority]:
        """List active tasks with dependency counts and inherited CD3 scores."""
        with get_connection(self.db_path) as conn, conn:
            conn.execute("BEGIN")
            tasks = [TaskWithDependencies.model_validate(dict(row)) for row in conn.execute("SELECT * FROM tasks_full")]
            priorities = _effective_priorities(conn, tasks)
        return [
            TaskWithPriority.model_validate(task.model_dump() | {"effective_priority": priorities[task.task_id]})
            for task in tasks
            if status is None or task.status == status
        ]

    def get_open_tasks_sorted(self) -> list[TaskWithPriority]:
        """Rank the active graph once by inherited CD3 descending."""
        return sorted(self.list_tasks_with_priority(), key=lambda task: task.effective_priority, reverse=True)

    def get_unblocked_tasks(self, tasks: list[TaskWithPriority] | None = None) -> list[TaskWithPriority]:
        """Return actionable tasks with no active blockers."""
        return [task for task in (self.get_open_tasks_sorted() if tasks is None else tasks) if not task.is_blocked]
