"""Agent dependency container for repository access."""

from dataclasses import dataclass

from ..database.dependency_repository import TaskDependencyRepository
from ..database.repository import TaskRepository


@dataclass
class TaskDependencies:
    """Container for task-related repositories.

    Provides both task and dependency repositories to agent tools,
    enabling dependency-aware operations.

    Attributes:
        task_repo: Repository for task CRUD operations.
        dep_repo: Repository for task dependency management.
    """

    task_repo: TaskRepository
    dep_repo: TaskDependencyRepository
