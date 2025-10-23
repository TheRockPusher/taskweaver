"""Agent dependency container for repository access."""

from dataclasses import dataclass

from ..database.dependency_repository import TaskDependencyRepository
from ..database.repository import TaskRepository


@dataclass
class TaskDependencies:
    """Container for task-related repositories and memory.

    Provides task repositories and semantic memory to agent tools,
    enabling dependency-aware operations and persistent memory.

    Attributes:
        task_repo: Repository for task CRUD operations.
        dep_repo: Repository for task dependency management.
        memory: Mem0 memory instance for semantic storage (optional).
        user_id: User identifier for memory operations (default: "default").

    """

    task_repo: TaskRepository
    dep_repo: TaskDependencyRepository
    memories: str
    user_id: str = "default"
