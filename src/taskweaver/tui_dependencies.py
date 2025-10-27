"""Dependency container for TUI.

This module provides dependency injection for TUI components,
following the same pattern as agents/dependencies.py.
"""

from dataclasses import dataclass
from pathlib import Path

from .database.dependency_repository import TaskDependencyRepository
from .database.repository import TaskRepository


@dataclass
class TuiDependencies:
    """Dependency container for TUI components.

    Follows project pattern from agents/dependencies.py for
    dependency injection and testability.

    This enables:
    - Dependency injection for testing (can inject mocks)
    - Loose coupling (TUI doesn't create dependencies)
    - Flexibility (can swap implementations)

    Attributes:
        task_repo: Repository for task CRUD operations.
        dep_repo: Repository for dependency management and priorities.
        db_path: Path to SQLite database.

    Example:
        >>> deps = TuiDependencies(
        ...     task_repo=TaskRepository(db_path),
        ...     dep_repo=TaskDependencyRepository(db_path),
        ...     db_path=db_path
        ... )
        >>> app = TaskWeaverApp(db_path, deps=deps)
    """

    task_repo: TaskRepository
    dep_repo: TaskDependencyRepository
    db_path: Path
