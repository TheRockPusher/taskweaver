"""Tests for TUI modal screens."""

from taskweaver.database.models import TaskStatus, TaskWithPriority
from taskweaver.tui.screens import TaskDetailScreen


def test_screen_stores_task():
    """Test screen creation and task storage."""
    task = TaskWithPriority(
        title="Test Task",
        description="Description",
        duration_min=45,
        llm_value=85.0,
        requirement="Must complete",
        status=TaskStatus.IN_PROGRESS,
        tasks_blocked_count=2,
        active_blocker_count=1,
        effective_priority=1.234,
    )
    screen = TaskDetailScreen(task)
    assert screen.task_data == task


def test_screen_with_none_description():
    """Test screen handles task with no description."""
    task = TaskWithPriority(
        title="Task",
        description=None,
        duration_min=30,
        llm_value=50.0,
        requirement="Requirement",
        status=TaskStatus.PENDING,
        tasks_blocked_count=0,
        active_blocker_count=0,
        effective_priority=1.667,
    )
    screen = TaskDetailScreen(task)
    assert screen.task_data.description is None
