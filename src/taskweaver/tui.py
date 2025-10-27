"""Terminal User Interface for TaskWeaver using Textual.

This module provides a rich TUI for interacting with TaskWeaver, featuring:
- Interactive chat interface with AI agent
- Live task tables showing open and unblocked tasks
- Real-time priority updates
- Terminal theme colors for consistent appearance
"""

from pathlib import Path
from typing import ClassVar

from loguru import logger
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.theme import Theme
from textual.widgets import DataTable, Footer, Header, Input, Markdown, Static

from .agents.chat_handler import TuiChatHandler
from .agents.task_agent import run_chat
from .database.dependency_repository import TaskDependencyRepository
from .database.exceptions import DependencyError, TaskNotFoundError
from .database.models import TaskStatus, TaskWithPriority
from .database.repository import TaskRepository

# Minimal terminal-like theme using neutral grays
terminal_theme = Theme(
    name="terminal",
    primary="#a8a8a8",  # Neutral gray
    secondary="#909090",  # Slightly darker gray
    accent="#b0b0b0",  # Subtle accent gray
    foreground="#d0d0d0",  # Light gray for text
    background="#1c1c1c",  # Very dark gray, almost black
    success="#90a959",  # Muted green
    warning="#f4bf75",  # Muted orange
    error="#ac4142",  # Muted red
    surface="#262626",  # Slightly lighter than background
    panel="#303030",  # Even lighter for panels
    dark=True,
    variables={
        "input-selection-background": "#404040",
        "border": "#606060",
    },
)


class TaskWeaverApp(App):
    """Main Textual TUI Application for TaskWeaver.

    Features:
    - Chat interface for AI agent interaction
    - Live task tables with priority sorting
    - Automatic refresh every 5 seconds
    - Keyboard shortcuts (q to quit, Ctrl+C to exit)
    """

    TITLE = "🧵 TaskWeaver"
    SUB_TITLE = "AI Task Manager"

    BINDINGS: ClassVar = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]

    CSS = """
    /* Theme-based styling for beautiful, themeable UI */

    /* Chat container - main surface with primary accent */
    #chat-container {
        height: 60%;
        background: $surface;
        border: round $primary;
        margin: 1;
    }

    #chat-view {
        padding: 1 2;
        background: $surface;
    }

    /* Tasks container - divided panels */
    #tasks-container {
        height: 40%;
        layout: horizontal;
        margin: 0 1 1 1;
    }

    #open-tasks {
        width: 1fr;
        background: $panel;
        border: round $primary-darken-1;
        margin: 0 1 0 0;
        padding: 1;
    }

    #unblocked-tasks {
        width: 1fr;
        background: $panel;
        border: round $primary-darken-1;
        padding: 1;
    }

    /* Message styling - colorful and distinct */
    .agent-message {
        background: $primary-muted;
        color: $text-primary;
        border-left: wide $primary;
        margin: 1 0;
        padding: 1 2;
    }

    .user-message {
        background: $secondary-muted;
        color: $text-secondary;
        border-left: wide $secondary;
        margin: 1 0;
        padding: 1 2;
    }

    .system-message {
        background: $surface-lighten-1;
        color: $text-muted;
        margin: 1 0;
        padding: 1 2;
    }

    .error-message {
        background: $error-muted;
        color: $text-error;
        border: solid $error;
        margin: 1 0;
        padding: 1 2;
    }

    /* Input - styled with focus effects */
    Input {
        dock: bottom;
        background: $surface;
        border: round $accent-darken-1;
        margin: 0 1 1 1;
        padding: 0 1;
    }

    Input:focus {
        border: heavy $accent;
        background: $surface-lighten-1;
    }

    /* Tables - styled with theme colors */
    DataTable {
        height: 100%;
        background: transparent;
    }

    DataTable > .datatable--header {
        background: $accent;
        color: $text-accent;
        text-style: bold;
    }

    .task-header {
        text-align: left;
        color: $primary;
        background: $surface-darken-1;
        text-style: bold;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the TaskWeaver TUI application.

        Args:
            db_path: Path to the SQLite database file.
        """
        super().__init__()
        self.db_path = db_path

        # Set up repositories for task display only
        self.task_repo = TaskRepository(db_path)
        self.dep_repo = TaskDependencyRepository(db_path)

        # Create TUI chat handler (run_chat will use this)
        self.chat_handler = TuiChatHandler(self)

        logger.info(f"TaskWeaver TUI initialized with database: {db_path}")

    def compose(self) -> ComposeResult:
        """Build UI layout.

        Yields:
            UI components in hierarchical order.
        """
        # Header with clock
        yield Header(show_clock=True)

        # Chat section (top 60%)
        with Container(id="chat-container"), VerticalScroll(id="chat-view"):
            yield Markdown("Type a message below to interact with TaskWeaver.")

        # Tasks section (bottom 40%)
        with Container(id="tasks-container"):
            with Container(id="open-tasks"):
                yield Static("Open Tasks (by Effective Priority)", classes="task-header")
                yield DataTable(id="open-tasks-table")
            with Container(id="unblocked-tasks"):
                yield Static("Unblocked Tasks", classes="task-header")
                yield DataTable(id="unblocked-tasks-table")

        # Input at bottom
        yield Input(placeholder="Type your message...")

        # Footer with keybindings
        yield Footer()

    def on_mount(self) -> None:
        """Initialize widgets, register theme, and start chat worker."""
        logger.debug("TUI mounted, initializing widgets")

        # Register and apply minimal terminal theme
        self.register_theme(terminal_theme)
        self.theme = "terminal"

        self.setup_task_tables()
        self.refresh_tasks()
        # Refresh task data every 5 seconds
        self.set_interval(5, self.refresh_tasks)

        # Start run_chat() in background worker thread
        self.start_chat_worker()

    @work(thread=True, exclusive=True)
    def start_chat_worker(self) -> None:
        """Run the shared run_chat() function in a worker thread.

        This runs the same agent loop as CLI, bridging blocking I/O
        with event-driven TUI via TuiChatHandler's queue.
        """
        logger.info("Starting chat worker thread")
        run_chat(self.chat_handler, self.db_path)
        logger.info("Chat worker thread ended")

    def setup_task_tables(self) -> None:
        """Configure DataTable columns for both task tables."""
        open_table = self.query_one("#open-tasks-table", DataTable)
        open_table.add_columns(
            "Title",
            "Priority",
            "Eff. Priority",
            "Status",
            "Blocked By",
        )

        unblocked_table = self.query_one("#unblocked-tasks-table", DataTable)
        unblocked_table.add_columns(
            "Title",
            "Priority",
            "Eff. Priority",
            "Status",
        )
        logger.debug("Task tables configured")

    def refresh_tasks(self) -> None:
        """Refresh task data from database.

        Queries pending and in-progress tasks, sorts by effective priority,
        and updates both task tables.
        """
        try:
            # Get all open tasks with priority
            pending_tasks = self.dep_repo.list_tasks_with_priority(status=TaskStatus.PENDING)
            in_progress_tasks = self.dep_repo.list_tasks_with_priority(status=TaskStatus.IN_PROGRESS)
            open_tasks = pending_tasks + in_progress_tasks

            # Sort by effective priority (descending)
            open_tasks.sort(key=lambda t: t.effective_priority, reverse=True)

            # Filter unblocked tasks
            unblocked_tasks = [t for t in open_tasks if not t.is_blocked]

            # Update tables
            self.update_open_tasks_table(open_tasks)
            self.update_unblocked_tasks_table(unblocked_tasks)

            logger.debug(f"Refreshed tasks: {len(open_tasks)} open, {len(unblocked_tasks)} unblocked")
        except (TaskNotFoundError, DependencyError) as e:
            logger.error(f"Database error refreshing tasks: {e}")
            self.post_error_message(f"Failed to refresh tasks: {e}")
        except OSError as e:
            logger.error(f"File system error refreshing tasks: {e}")
            self.post_error_message(f"Database access error: {e}")

    def update_open_tasks_table(self, tasks: list[TaskWithPriority]) -> None:
        """Update open tasks DataTable.

        Args:
            tasks: List of tasks with priority information.
        """
        table = self.query_one("#open-tasks-table", DataTable)
        table.clear()
        for task in tasks:
            table.add_row(
                task.title[:30],  # Truncate long titles
                f"{task.priority:.3f}",
                f"{task.effective_priority:.3f}",
                task.status,
                str(task.active_blocker_count),
            )

    def update_unblocked_tasks_table(self, tasks: list[TaskWithPriority]) -> None:
        """Update unblocked tasks DataTable.

        Args:
            tasks: List of unblocked tasks with priority information.
        """
        table = self.query_one("#unblocked-tasks-table", DataTable)
        table.clear()
        for task in tasks:
            table.add_row(
                task.title[:30],
                f"{task.priority:.3f}",
                f"{task.effective_priority:.3f}",
                task.status,
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission.

        Args:
            event: The input submission event containing user text.
        """
        user_input = event.value.strip()

        if not user_input:
            return

        # Clear input field
        event.input.value = ""

        # Display user message
        chat_view = self.query_one("#chat-view", VerticalScroll)
        chat_view.mount(Markdown(f"**You:** {user_input}", classes="user-message"))
        chat_view.scroll_end(animate=False)

        # Check for exit commands
        if user_input.lower() in ("exit", "quit", "bye"):
            logger.info("User requested exit via input")
            self.chat_handler.should_exit = True
            self.chat_handler.input_queue.put(None)
            self.exit()
            return

        # Put input in queue for run_chat() worker to process
        self.chat_handler.input_queue.put(user_input)
        logger.debug(f"User input queued for agent: {user_input[:50]}...")

    def post_agent_message(self, message: str) -> None:
        """Display agent message in chat view.

        Args:
            message: Agent's response message, may contain markdown.
        """
        chat_view = self.query_one("#chat-view", VerticalScroll)
        chat_view.mount(Markdown(f"**TaskWeaver:** {message}", classes="agent-message"))
        chat_view.scroll_end(animate=False)

    def post_system_message(self, message: str) -> None:
        """Display system message in chat view.

        Args:
            message: System notification message.
        """
        chat_view = self.query_one("#chat-view", VerticalScroll)
        chat_view.mount(Markdown(f"*{message}*", classes="system-message"))

    def post_error_message(self, message: str) -> None:
        """Display error message in chat view.

        Args:
            message: Error message text.
        """
        chat_view = self.query_one("#chat-view", VerticalScroll)
        chat_view.mount(Markdown(f"**ERROR:** {message}", classes="error-message"))
        chat_view.scroll_end(animate=False)


def run_tui(db_path: Path) -> None:
    """Entry point to run the TUI application.

    Args:
        db_path: Path to the SQLite database file.
    """
    # Configure loguru to write to file only (prevents terminal corruption)
    logger.remove()  # Remove all handlers including default stderr

    # Set up log file
    log_dir = Path.home() / ".taskweaver"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "tui.log"

    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.info("Starting TaskWeaver TUI")
    app = TaskWeaverApp(db_path)
    app.run()
