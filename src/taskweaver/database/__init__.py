"""Database module for TaskWeaver."""

from .completion_repository import CompletionRepository
from .connection import get_connection, init_database
from .exceptions import CompletionNotFoundError, TaskNotFoundError
from .models import Completion, CompletionCreate, CompletionStatus, Task, TaskCreate, TaskStatus, TaskUpdate
from .repository import TaskRepository

__all__ = [
    "Completion",
    "CompletionCreate",
    "CompletionNotFoundError",
    "CompletionRepository",
    "CompletionStatus",
    "Task",
    "TaskCreate",
    "TaskNotFoundError",
    "TaskRepository",
    "TaskStatus",
    "TaskUpdate",
    "get_connection",
    "init_database",
]
