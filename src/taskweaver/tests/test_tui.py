"""Tests for TaskWeaver TUI application.

Tests use minimal mocking - only worker threads and agent interaction are mocked.
Real database operations are tested with temporary test databases.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import DataTable, Footer, Header, Input

from taskweaver.database.connection import init_database
from taskweaver.database.models import TaskCreate, TaskStatus, TaskUpdate
from taskweaver.database.repository import TaskRepository
from taskweaver.tui import TaskWeaverApp
from taskweaver.tui_constants import MAX_CHAT_MESSAGES


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Initialize database schema
    init_database(db_path)

    # Add some test tasks
    repo = TaskRepository(db_path)
    repo.create_task(
        TaskCreate(
            title="Test Task 1",
            description="First test task",
            duration_min=30,
            llm_value=8.5,
            requirement="Must complete",
        )
    )
    task2 = repo.create_task(
        TaskCreate(
            title="Test Task 2",
            description="Second test task",
            duration_min=45,
            llm_value=7.0,
            requirement="Should finish",
        )
    )
    # Update status after creation
    repo.update_task(task2.task_id, TaskUpdate(status=TaskStatus.IN_PROGRESS))

    yield db_path

    # Cleanup
    db_path.unlink()


@pytest.fixture
def app(test_db):
    """Create TUI app instance with test database."""
    # Patch the worker to prevent it from starting
    with patch.object(TaskWeaverApp, "start_chat_worker", return_value=None):
        app_instance = TaskWeaverApp(test_db)
        yield app_instance


class TestTUIInitialization:
    """Test TUI app initialization and composition."""

    async def test_app_creation(self, app):
        """Test that app can be created successfully."""
        assert app is not None
        assert app.db_path.exists()
        assert app.task_repo is not None
        assert app.dep_repo is not None
        assert app.chat_handler is not None

    async def test_app_title(self, app):
        """Test app title and subtitle are set correctly."""
        assert app.TITLE == "🧵 TaskWeaver"
        assert app.SUB_TITLE == "AI Task Manager"

    async def test_widget_composition(self, app):
        """Test that all required widgets are composed."""
        async with app.run_test() as pilot:
            # Wait for widgets to mount
            await pilot.pause()

            # Check for Header
            assert app.query_one(Header) is not None

            # Check for Footer
            assert app.query_one(Footer) is not None

            # Check for Input widget
            assert app.query_one(Input) is not None

            # Check for task tables
            tables = app.query(DataTable)
            assert len(tables) == 2  # open-tasks-table and unblocked-tasks-table


class TestMessagePosting:
    """Test message posting methods."""

    async def test_post_agent_message(self, app):
        """Test posting agent message to chat view."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Count initial messages
            initial_count = len(app.query("#chat-view Markdown"))

            # Post agent message
            app.post_agent_message("Hello from agent")
            await pilot.pause()

            # Check message was added
            chat_messages = app.query("#chat-view Markdown")
            assert len(chat_messages) == initial_count + 1

            # Verify it's a Markdown widget with agent-message class
            last_message = chat_messages[-1]
            assert last_message.has_class("agent-message")

    async def test_post_system_message(self, app):
        """Test posting system message to chat view."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Post system message
            app.post_system_message("System notification")
            await pilot.pause()

            # Check message appears
            messages = app.query("#chat-view Markdown")
            assert len(messages) > 1

    async def test_post_error_message(self, app):
        """Test posting error message to chat view."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Count initial messages
            initial_count = len(app.query("#chat-view Markdown"))

            # Post error message
            app.post_error_message("Something went wrong")
            await pilot.pause()

            # Check error message was added
            messages = app.query("#chat-view Markdown")
            assert len(messages) == initial_count + 1

            # Verify it has the error-message class
            last_message = messages[-1]
            assert last_message.has_class("error-message")


class TestTaskTables:
    """Test task table functionality."""

    async def test_task_tables_setup(self, app):
        """Test that task tables are set up with correct columns."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get both tables
            open_table = app.query_one("#open-tasks-table", DataTable)
            unblocked_table = app.query_one("#unblocked-tasks-table", DataTable)

            # Check open tasks table has correct number of columns
            assert len(open_table.columns) == 5

            # Check unblocked tasks table has correct number of columns
            assert len(unblocked_table.columns) == 4

    async def test_task_tables_refresh(self, app):
        """Test that task tables show data from database."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Trigger refresh
            app.refresh_tasks()
            await pilot.pause()

            # Check that tables have data
            open_table = app.query_one("#open-tasks-table", DataTable)

            # Should have rows from test database
            assert open_table.row_count >= 2  # We added 2 tasks in fixture


class TestInputHandling:
    """Test input handling and queue interaction."""

    async def test_input_submission(self, app):
        """Test that input submission queues user input."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get input widget
            input_widget = app.query_one(Input)

            # Simulate user typing
            input_widget.value = "test message"
            await pilot.pause()

            # Submit input
            await pilot.press("enter")
            await pilot.pause()

            # Check input was cleared
            assert input_widget.value == ""

            # Check message was queued
            assert not app.chat_handler.input_queue.empty()
            queued_msg = app.chat_handler.input_queue.get_nowait()
            assert queued_msg == "test message"

    async def test_exit_commands(self, app):
        """Test that exit commands set exit flag."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get input widget
            input_widget = app.query_one(Input)

            # Test 'exit' command
            input_widget.value = "exit"
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            # Check exit flag is set
            assert app.chat_handler.should_exit


class TestChatHandlerIntegration:
    """Test TuiChatHandler integration with the app."""

    def test_chat_handler_initialization(self, app):
        """Test that chat handler is properly initialized."""
        handler = app.chat_handler
        assert handler is not None
        assert handler.app is app
        assert handler.input_queue is not None
        assert handler.should_exit is False

    async def test_chat_handler_display_methods(self, app):
        """Test chat handler display methods delegate to app correctly."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Test that methods exist and can be called
            # Note: We test via app.post_* methods directly since call_from_thread
            # requires actual threading which is difficult to test
            app.post_agent_message("Test agent message")
            await pilot.pause()

            app.post_system_message("Test system message")
            await pilot.pause()

            app.post_error_message("Test error message")
            await pilot.pause()

            # Verify messages appear in chat view
            messages = app.query("#chat-view Markdown")
            assert len(messages) >= 3  # Initial + 3 test messages


class TestRepositoryMethods:
    """Test new repository methods used by TUI."""

    async def test_get_open_tasks_sorted(self, app):
        """Test that TUI uses repository method for sorted tasks."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get tasks through repository method
            tasks = app.dep_repo.get_open_tasks_sorted()

            # Should be sorted by effective priority descending
            assert len(tasks) >= 2
            # Verify sorted order
            for i in range(len(tasks) - 1):
                assert tasks[i].effective_priority >= tasks[i + 1].effective_priority

    async def test_get_unblocked_tasks(self, app):
        """Test filtering for unblocked tasks."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get all open tasks
            open_tasks = app.dep_repo.get_open_tasks_sorted()

            # Get unblocked tasks
            unblocked = app.dep_repo.get_unblocked_tasks(open_tasks)

            # All unblocked tasks should have no active blockers
            for task in unblocked:
                assert not task.is_blocked


class TestKeyboardShortcuts:
    """Test keyboard shortcuts and bindings."""

    async def test_quit_binding(self, app):
        """Test that 'q' key quits the app."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Press 'q' to quit
            await pilot.press("q")
            await pilot.pause()

            # App should exit (we can't easily test this, but we can verify binding exists)
            assert ("q", "quit", "Quit") in app.BINDINGS


class TestShutdownBehavior:
    """Test clean shutdown and resource cleanup."""

    async def test_on_unmount_pushes_sentinel_to_unblock_worker(self, app):
        """Test that on_unmount pushes sentinel to wake up blocked worker.

        Regression test for thread leak bug where worker was blocked on
        input_queue.get() and couldn't observe cancellation. The fix ensures
        that on_unmount pushes None to the queue before cancelling workers.
        """
        async with app.run_test() as pilot:
            await pilot.pause()

            # Verify initial state
            assert app.chat_handler.should_exit is False
            assert app.chat_handler.input_queue.empty()

            # Simulate unmount (what happens when user presses 'q')
            app.on_unmount()

            # Verify sentinel was pushed to queue to wake up blocked worker
            assert app.chat_handler.should_exit is True
            item = app.chat_handler.input_queue.get_nowait()
            assert item is None, "Sentinel should be None to unblock get()"
