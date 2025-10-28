"""Tests for TUI modal screens."""

from unittest.mock import patch

from textual.widgets import Button

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


def test_screen_stores_task_with_description():
    """Test screen stores task with description correctly."""
    task = TaskWithPriority(
        title="Compose Test",
        description="Testing compose method",
        duration_min=60,
        llm_value=90.0,
        requirement="Test requirement",
        status=TaskStatus.PENDING,
        tasks_blocked_count=3,
        active_blocker_count=1,
        effective_priority=2.5,
    )
    screen = TaskDetailScreen(task)

    assert screen.task_data.title == "Compose Test"
    assert screen.task_data.description == "Testing compose method"
    assert screen.task_data.duration_min == 60


def test_screen_has_bindings():
    """Test screen has escape binding defined."""
    task = TaskWithPriority(
        title="Task with Description",
        description="This is a description",
        duration_min=30,
        llm_value=50.0,
        requirement="Requirement",
        status=TaskStatus.PENDING,
        tasks_blocked_count=0,
        active_blocker_count=0,
        effective_priority=1.667,
    )
    screen = TaskDetailScreen(task)

    assert hasattr(screen, "BINDINGS")
    assert len(screen.BINDINGS) > 0
    assert any(binding[0] == "escape" for binding in screen.BINDINGS)


def test_screen_stores_all_task_fields():
    """Test screen stores all task fields correctly."""
    task = TaskWithPriority(
        title="Complete Task",
        description="Full description",
        duration_min=90,
        llm_value=95.0,
        requirement="All requirements",
        status=TaskStatus.IN_PROGRESS,
        tasks_blocked_count=5,
        active_blocker_count=2,
        effective_priority=3.5,
    )
    screen = TaskDetailScreen(task)

    assert screen.task_data.llm_value == 95.0
    assert screen.task_data.tasks_blocked_count == 5
    assert screen.task_data.active_blocker_count == 2
    assert screen.task_data.effective_priority == 3.5


def test_button_pressed_dismisses_modal():
    """Test on_button_pressed() dismisses modal when close button clicked."""
    task = TaskWithPriority(
        title="Button Test",
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

    button = Button("Close", id="close-button")
    event = Button.Pressed(button)

    with patch.object(screen, "dismiss") as mock_dismiss:
        screen.on_button_pressed(event)
        mock_dismiss.assert_called_once()
