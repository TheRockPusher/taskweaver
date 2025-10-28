"""Constants for TUI configuration.

This module centralizes all magic numbers and widget IDs to improve
maintainability and prevent typos.
"""

# Layout proportions (percentages)
CHAT_HEIGHT_PERCENT = 60
TASKS_HEIGHT_PERCENT = 40

# Display limits
MAX_TITLE_LENGTH = 30
MAX_CHAT_MESSAGES = 100

# Refresh intervals (seconds)
REFRESH_INTERVAL_SECONDS = 5

# TextArea configuration
MAX_TEXTAREA_HEIGHT = "20%"  # Max height as percentage of screen
DEFAULT_EDITOR = "vim"  # Fallback if EDITOR not set
EDITOR_FALLBACK_CHAIN = ["vim", "nano", "vi"]  # Try in order


class WidgetIDs:
    """Widget ID constants (prevents typos, enables refactoring).

    Using constants for widget IDs provides:
    - IDE autocomplete
    - Type safety
    - Easier refactoring
    - Self-documentation
    """

    CHAT_VIEW = "chat-view"
    CHAT_CONTAINER = "chat-container"
    TASKS_CONTAINER = "tasks-container"
    OPEN_TASKS = "open-tasks"
    OPEN_TASKS_TABLE = "open-tasks-table"
    UNBLOCKED_TASKS = "unblocked-tasks"
    UNBLOCKED_TASKS_TABLE = "unblocked-tasks-table"
