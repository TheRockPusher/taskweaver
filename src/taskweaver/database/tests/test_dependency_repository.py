"""Tests for task dependency repository."""

from uuid import UUID, uuid4

import pytest

from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.exceptions import DependencyError, TaskNotFoundError
from taskweaver.database.models import TaskCreate
from taskweaver.database.repository import TaskRepository


@pytest.fixture
def tasks(task_repo: TaskRepository) -> dict[str, UUID]:
    """Create sample tasks for testing.

    Returns:
        Dict mapping task names to UUIDs.
    """
    return {
        "A": task_repo.create_task(
            TaskCreate(title="Task A", duration_min=30, llm_value=5.0, requirement="Test requirement")
        ).task_id,
        "B": task_repo.create_task(
            TaskCreate(title="Task B", duration_min=30, llm_value=5.0, requirement="Test requirement")
        ).task_id,
        "C": task_repo.create_task(
            TaskCreate(title="Task C", duration_min=30, llm_value=5.0, requirement="Test requirement")
        ).task_id,
        "D": task_repo.create_task(
            TaskCreate(title="Task D", duration_min=30, llm_value=5.0, requirement="Test requirement")
        ).task_id,
    }


# Add Dependency Tests


def test_add_dependency_success(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test creating a dependency between two tasks."""
    dep = dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])

    assert dep.task_id == tasks["A"]
    assert dep.blocker_id == tasks["B"]
    assert dep.dependency_id is not None


def test_add_dependency_closed_task_fails(
    dep_repo: TaskDependencyRepository, task_repo: TaskRepository, tasks: dict[str, UUID]
) -> None:
    """Test adding dependency with completed task fails."""
    task_repo.mark_completed(tasks["A"])

    with pytest.raises(DependencyError, match="task is closed"):
        dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])


def test_add_dependency_nonexistent_task_fails(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test adding dependency with non-existent task fails."""
    with pytest.raises(TaskNotFoundError):
        dep_repo.add_dependency(task_id=uuid4(), blocker_id=tasks["B"])


# Remove Dependency Tests


def test_remove_dependency_success(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test removing an existing dependency."""
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])

    dep_repo.remove_dependency(task_id=tasks["A"], blocker_id=tasks["B"])

    # Verify removal - no blockers should exist
    blockers = dep_repo.get_blockers(tasks["A"])
    assert len(blockers) == 0


def test_remove_nonexistent_dependency_fails(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test removing non-existent dependency raises error."""
    with pytest.raises(DependencyError, match="Dependency not found"):
        dep_repo.remove_dependency(task_id=tasks["A"], blocker_id=tasks["B"])


# Get Blockers Tests


def test_get_blockers_empty(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test getting blockers when none exist."""
    blockers = dep_repo.get_blockers(tasks["A"])
    assert blockers == []


def test_get_blockers_single(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test getting single blocker."""
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])

    blockers = dep_repo.get_blockers(tasks["A"])

    assert len(blockers) == 1
    assert blockers[0].task_id == tasks["B"]


def test_get_blockers_multiple(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test getting multiple blockers."""
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["C"])

    blockers = dep_repo.get_blockers(tasks["A"])

    expected_blocker_count = 2
    assert len(blockers) == expected_blocker_count
    blocker_ids = {b.task_id for b in blockers}
    assert blocker_ids == {tasks["B"], tasks["C"]}


def test_get_blockers_only_active(
    dep_repo: TaskDependencyRepository, task_repo: TaskRepository, tasks: dict[str, UUID]
) -> None:
    """Test get_blockers returns only pending/in_progress tasks."""
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["C"])

    # Complete one blocker
    task_repo.mark_completed(tasks["B"])

    blockers = dep_repo.get_blockers(tasks["A"])

    # Only C should remain (B is completed)
    assert len(blockers) == 1
    assert blockers[0].task_id == tasks["C"]


# Get Blocked Tests


def test_get_blocked_empty(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test getting blocked tasks when none exist."""
    blocked = dep_repo.get_blocked(tasks["A"])
    assert blocked == []


def test_get_blocked_single(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test getting single blocked task."""
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])

    blocked = dep_repo.get_blocked(tasks["B"])

    assert len(blocked) == 1
    assert blocked[0].task_id == tasks["A"]


def test_get_blocked_multiple(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test getting multiple blocked tasks."""
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["C"])
    dep_repo.add_dependency(task_id=tasks["B"], blocker_id=tasks["C"])

    blocked = dep_repo.get_blocked(tasks["C"])

    expected_blocked_count = 2
    assert len(blocked) == expected_blocked_count
    blocked_ids = {t.task_id for t in blocked}
    assert blocked_ids == {tasks["A"], tasks["B"]}


# Cycle Check Tests


def test_cycle_check_no_cycle(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test cycle detection when no cycle exists."""
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])
    dep_repo.add_dependency(task_id=tasks["B"], blocker_id=tasks["C"])

    # D -> A should not create a cycle
    has_cycle = dep_repo._cycle_check(tasks["A"], tasks["D"])
    assert has_cycle is False


def test_cycle_check_direct_cycle(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test detection of direct cycle (A -> B -> A)."""
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])

    # B -> A would create direct cycle
    has_cycle = dep_repo._cycle_check(tasks["B"], tasks["A"])
    assert has_cycle is True


def test_cycle_check_transitive_cycle(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test detection of transitive cycle (A -> B -> C -> A)."""
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])
    dep_repo.add_dependency(task_id=tasks["B"], blocker_id=tasks["C"])

    # C -> A would create transitive cycle
    has_cycle = dep_repo._cycle_check(tasks["C"], tasks["A"])
    assert has_cycle is True


def test_cycle_check_self_reference(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test detection of self-referencing cycle (A -> A)."""
    has_cycle = dep_repo._cycle_check(tasks["A"], tasks["A"])
    assert has_cycle is True


def test_cycle_check_complex_graph(dep_repo: TaskDependencyRepository, tasks: dict[str, UUID]) -> None:
    """Test cycle detection in complex dependency graph."""
    # Create graph: A -> B, A -> C, B -> D, C -> D
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["B"])
    dep_repo.add_dependency(task_id=tasks["A"], blocker_id=tasks["C"])
    dep_repo.add_dependency(task_id=tasks["B"], blocker_id=tasks["D"])
    dep_repo.add_dependency(task_id=tasks["C"], blocker_id=tasks["D"])

    # D -> A would create cycle through multiple paths (D->B->A or D->C->A)
    has_cycle = dep_repo._cycle_check(tasks["D"], tasks["A"])
    assert has_cycle is True

    # D -> B would also create cycle (D->B->D already exists)
    has_cycle = dep_repo._cycle_check(tasks["D"], tasks["B"])
    assert has_cycle is True

    has_cycle = dep_repo._cycle_check(tasks["A"], tasks["D"])
    assert has_cycle is False
