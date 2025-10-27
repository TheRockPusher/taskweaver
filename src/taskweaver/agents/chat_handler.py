"""Chat handler implementations for agent-user communication.

This module provides abstractions for handling conversational I/O between
the AI agent and users across different interfaces (CLI, web, etc.).
"""

import queue
from typing import TYPE_CHECKING, Protocol

from rich.console import Console
from rich.markdown import Markdown

if TYPE_CHECKING:
    from ..tui import TaskWeaverApp


class ChatHandler(Protocol):
    """Protocol for general I/O operations.

    Defines the interface for handling bidirectional communication
    between the AI agent and users.
    """

    def display_agent_message(self, message: str) -> None:
        """Display a message from the AI agent to the user.

        Args:
            message: The message text to display, may contain markdown.
        """
        ...

    def get_user_input(self, prompt: str = "") -> str | None:
        """Get input from the user.

        Args:
            prompt: Optional prompt to display before accepting input.

        Returns:
            User input string, or None if user requests to exit.
        """
        ...

    def display_system_message(self, message: str) -> None:
        """Display a message from the system."""
        ...

    def display_error(self, message: str) -> None:
        """Display an error message."""
        ...


class CliChatHandler:
    """Chat Handler for CLI usage."""

    def __init__(self) -> None:
        self.console = Console()

    def display_agent_message(self, message: str) -> None:
        """Displays the message coming from the AI agent."""
        self.console.print("[cyan]TaskWeaver:[/cyan]", end=" ")
        self.console.print(Markdown(message))
        self.console.print()  # Blank line

    def get_user_input(self, prompt: str = "") -> str | None:
        """Agent can use this to get the user input."""
        try:
            user_input = self.console.input(f"[bold green]{prompt}[/bold green]")
            if user_input.lower() in ("exit", "quit", "bye"):
                self.console.print("\n[blue]GOODBYE[/blue]")
                return None
            return user_input
        except (EOFError, KeyboardInterrupt):
            self.console.print("\n[blue]GOODBYE[/blue]")
            return None

    def display_system_message(self, message: str) -> None:
        """Display a message from the system."""
        self.console.print(f"[green]{message}[/green]")

    def display_error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(f"[red]ERROR: {message}[/red]")


class TuiChatHandler:
    """Chat Handler for TUI usage.

    Bridges blocking I/O (run_chat) with event-driven TUI using queue.Queue.
    Handler runs in worker thread, UI updates via call_from_thread.
    """

    def __init__(self, app: "TaskWeaverApp") -> None:
        """Initialize the TUI chat handler.

        Args:
            app: The main TaskWeaver TUI application instance.
        """
        self.app = app
        self.input_queue: queue.Queue[str | None] = queue.Queue()
        self.should_exit = False

    def display_agent_message(self, message: str) -> None:
        """Display a message from the AI agent (called from worker thread).

        Args:
            message: The message text to display, may contain markdown.
        """
        # Use call_from_thread for thread safety
        self.app.call_from_thread(self.app.post_agent_message, message)

    def get_user_input(self, prompt: str = "") -> str | None:  # noqa: ARG002
        """Get input from the user (blocks until input available).

        This blocks the worker thread until user submits input.
        Called from run_chat() loop in worker thread.

        Args:
            prompt: Optional prompt (not used in TUI).

        Returns:
            User input string, or None if user requests to exit.
        """
        if self.should_exit:
            return None

        try:
            # Block until input available (bridges event-driven → blocking)
            # This is OK because we're in a worker thread
            input_text = self.input_queue.get()
            return input_text
        except (queue.Empty, RuntimeError):
            return None

    def display_system_message(self, message: str) -> None:
        """Display a message from the system (called from worker thread).

        Args:
            message: System message to display.
        """
        self.app.call_from_thread(self.app.post_system_message, message)

    def display_error(self, message: str) -> None:
        """Display an error message (called from worker thread).

        Args:
            message: Error message to display.
        """
        self.app.call_from_thread(self.app.post_error_message, message)
