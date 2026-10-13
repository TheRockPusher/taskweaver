"""Agent dependency container for repository access."""

from dataclasses import dataclass

from ..database.completion_repository import CompletionRepository
from ..database.dependency_repository import TaskDependencyRepository
from ..database.planning import PlanningService
from ..database.repository import TaskRepository
from .memory import MemoryService


@dataclass
class TaskDependencies:
    """Repositories and optional services plus request-scoped instructions.

    Memory facts are authoritative locally; semantic retrieval is explicitly injected.
    Orchestration replaces this container per turn so modes never leak between requests.
    """

    task_repo: TaskRepository
    dep_repo: TaskDependencyRepository
    completion_repo: CompletionRepository
    memories: str
    user_id: str = "default"
    planning: PlanningService | None = None
    memory: MemoryService | None = None
    request_mode: str | None = None
    request_instructions: str = ""
