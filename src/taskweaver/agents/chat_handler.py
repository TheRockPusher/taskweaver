"""Chat handler implementations for agent-user communication.

This module provides abstractions for handling conversational I/O between
the AI agent and users across different interfaces (CLI, web, etc.).
"""

from typing import Protocol

from rich.console import Console
from rich.markdown import Markdown


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
