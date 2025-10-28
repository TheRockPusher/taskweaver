"""Tests for TaskWeaver TUI application.

Tests use minimal mocking - only worker threads and agent interaction are mocked.
Real database operations are tested with temporary test databases.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import DataTable, Footer, Header, TextArea

from taskweaver.database.connection import init_database
from taskweaver.database.models import TaskCreate, TaskStatus, TaskUpdate, TaskWithPriority
from taskweaver.database.repository import TaskRepository
from taskweaver.tui import TaskWeaverApp
from taskweaver.tui.screens import TaskDetailScreen


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

            # Check for TextArea widget
            assert app.query_one(TextArea) is not None

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
            assert len(open_table.columns) == 6  # Title, Duration, Priority, Eff. Priority, Status, Blocked By

            # Check unblocked tasks table has correct number of columns
            assert len(unblocked_table.columns) == 6  # Title, Duration, Requirement, Priority, Eff. Priority, Status

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
        """Test that TextArea submission queues user input."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get TextArea widget
            text_area = app.query_one(TextArea)

            # Simulate user typing
            text_area.text = "test message"
            await pilot.pause()

            # Submit input with Ctrl+Enter
            await pilot.press("ctrl+enter")
            await pilot.pause()

            # Check TextArea was cleared
            assert text_area.text == ""

            # Check message was queued
            assert not app.chat_handler.input_queue.empty()
            queued_msg = app.chat_handler.input_queue.get_nowait()
            assert queued_msg == "test message"

    async def test_exit_commands(self, app):
        """Test that exit commands set exit flag."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get TextArea widget
            text_area = app.query_one(TextArea)

            # Test 'exit' command
            text_area.text = "exit"
            await pilot.pause()

            await pilot.press("ctrl+enter")
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


class TestModalIntegration:
    """Test modal screen integration with main app."""

    async def test_row_mappings_initialized(self, app):
        """Test that row mappings are initialized on app creation."""
        assert hasattr(app, "open_tasks_map")
        assert hasattr(app, "unblocked_tasks_map")
        assert isinstance(app.open_tasks_map, dict)
        assert isinstance(app.unblocked_tasks_map, dict)

    async def test_row_mappings_populated_on_refresh(self, app):
        """Test that row mappings are populated when tasks refresh."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Trigger refresh
            app.refresh_tasks()
            await pilot.pause()

            # Mappings should be populated
            assert len(app.open_tasks_map) >= 2  # We have 2 test tasks
            assert len(app.unblocked_tasks_map) >= 0

    async def test_open_tasks_row_selection_handler_exists(self, app):
        """Test that open tasks table has row selection handler configured."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Verify handler method exists
            assert hasattr(app, "on_open_tasks_row_selected")
            assert callable(app.on_open_tasks_row_selected)

    async def test_unblocked_tasks_row_selection_handler_exists(self, app):
        """Test that unblocked tasks table has row selection handler configured."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Verify handler method exists
            assert hasattr(app, "on_unblocked_tasks_row_selected")
            assert callable(app.on_unblocked_tasks_row_selected)

    async def test_can_create_modal_with_task(self, app):
        """Test that modal can be created with task data from mapping."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Ensure tables are populated
            app.refresh_tasks()
            await pilot.pause()

            # Get first task from open_tasks_map
            if app.open_tasks_map:
                first_row_key = next(iter(app.open_tasks_map.keys()))
                expected_task = app.open_tasks_map[first_row_key]

                # Create modal directly (simulating what handler does)
                modal = TaskDetailScreen(expected_task)
                assert modal.task_data.task_id == expected_task.task_id
                assert modal.task_data.title == expected_task.title

    async def test_modal_has_escape_binding(self):
        """Test that modal has escape binding configured."""
        task = TaskWithPriority(
            title="Test Task",
            duration_min=30,
            llm_value=50.0,
            requirement="Test",
            status=TaskStatus.PENDING,
            tasks_blocked_count=0,
            active_blocker_count=0,
            effective_priority=1.0,
        )
        modal = TaskDetailScreen(task)

        # Verify escape binding exists
        assert any(binding[0] == "escape" for binding in modal.BINDINGS)

    async def test_row_mapping_updates_on_refresh(self, app):
        """Test that row mappings are updated when tables refresh."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Initial refresh
            app.refresh_tasks()
            await pilot.pause()

            # Store initial mapping size
            initial_open_count = len(app.open_tasks_map)

            # Refresh again
            app.refresh_tasks()
            await pilot.pause()

            # Mappings should still be populated
            assert len(app.open_tasks_map) > 0
            assert len(app.unblocked_tasks_map) >= 0

            # Count should be consistent (no tasks were added/removed)
            assert len(app.open_tasks_map) == initial_open_count

    async def test_tables_have_row_cursor_enabled(self, app):
        """Test that tables have row cursor enabled for navigation."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get both tables
            open_table = app.query_one("#open-tasks-table", DataTable)
            unblocked_table = app.query_one("#unblocked-tasks-table", DataTable)

            # Verify cursor_type is set to "row"
            assert open_table.cursor_type == "row"
            assert unblocked_table.cursor_type == "row"


class TestCursorPreservation:
    """Test cursor position preservation during table refreshes."""

    async def test_cursor_preserved_in_open_tasks_on_refresh(self, app):
        """Test cursor stays at same position after refresh."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get open tasks table and move cursor to row 1
            open_table = app.query_one("#open-tasks-table", DataTable)
            open_table.move_cursor(row=1)

            initial_cursor = open_table.cursor_coordinate
            assert initial_cursor.row == 1

            # Trigger refresh
            app.refresh_tasks()
            await pilot.pause()

            # Cursor should still be at row 1
            final_cursor = open_table.cursor_coordinate
            assert final_cursor.row == 1
            assert final_cursor.row == initial_cursor.row

    async def test_cursor_preserved_in_unblocked_tasks_on_refresh(self, app):
        """Test cursor stays at same position after refresh in unblocked table."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Get unblocked tasks table and move cursor to row 1
            unblocked_table = app.query_one("#unblocked-tasks-table", DataTable)

            # Only test if table has rows
            if unblocked_table.row_count > 1:
                unblocked_table.move_cursor(row=1)
                initial_cursor = unblocked_table.cursor_coordinate

                # Trigger refresh
                app.refresh_tasks()
                await pilot.pause()

                # Cursor should still be at row 1
                final_cursor = unblocked_table.cursor_coordinate
                assert final_cursor.row == initial_cursor.row

    async def test_cursor_clamps_when_table_shrinks(self, app, test_db):
        """Test cursor resets if table shrinks below saved position."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Move cursor to last row
            open_table = app.query_one("#open-tasks-table", DataTable)
            if open_table.row_count > 0:
                last_row = open_table.row_count - 1
                open_table.move_cursor(row=last_row)

                # Mark all tasks as completed (should shrink open tasks table)
                repo = TaskRepository(test_db)
                tasks = repo.list_tasks(status=TaskStatus.PENDING)
                for task in tasks:
                    repo.update_task(task.task_id, TaskUpdate(status=TaskStatus.COMPLETED))

                # Trigger refresh
                app.refresh_tasks()
                await pilot.pause()

                # Cursor should be clamped (at 0 if table is now empty)
                final_cursor = open_table.cursor_coordinate
                assert final_cursor.row < open_table.row_count or open_table.row_count == 0

    async def test_cursor_handles_empty_table(self, app, test_db):
        """Test cursor preservation doesn't crash on empty table."""
        async with app.run_test() as pilot:
            await pilot.pause()

            # Complete all tasks
            repo = TaskRepository(test_db)
            tasks = repo.list_tasks()
            for task in tasks:
                repo.update_task(task.task_id, TaskUpdate(status=TaskStatus.COMPLETED))

            # Refresh should handle empty table gracefully
            app.refresh_tasks()
            await pilot.pause()

            # No assertion needed - just verify no crash
            open_table = app.query_one("#open-tasks-table", DataTable)
            assert open_table.row_count == 0
