"""Configuration management following XDG Base Directory Specification.

This module provides XDG-compliant paths and configuration loading from TOML files.
Follows Linux standards for config, data, cache, and state directories.

Configuration Hierarchy (later overrides earlier):
    1. Built-in defaults
    2. XDG user config (~/.config/taskweaver/config.toml)
    3. Project-local config (./config.toml) - takes precedence!

Environment Variables (.env):
    - Loaded from ./.env (project-local) or ~/.config/taskweaver/.env
    - Provider-specific API keys (see examples below)

    OpenAI models (gpt-4o, gpt-4o-mini, etc.):
        OPENAI_API_KEY=sk-...

    OpenRouter (multi-provider gateway):
        OPENROUTER_API_KEY=sk-or-...

    Anthropic models (claude-3-5-sonnet, etc.):
        ANTHROPIC_API_KEY=sk-ant-...

    Google models (gemini-1.5-flash, etc.):
        GOOGLE_API_KEY=...

    Note: TaskWeaver uses PydanticAI which requires provider-specific
    environment variables. Set the appropriate key for your model provider.

Directory Structure:
    # Project-local (for development)
    ./config.toml                      - Project-specific preferences
    ./.env                             - Project API keys (gitignored)
    ./tasks.db                         - Optional local database

    # XDG user directories (system-wide)
    ~/.config/taskweaver/config.toml   - User preferences
    ~/.config/taskweaver/.env          - API keys (secrets)
    ~/.local/share/taskweaver/tasks.db - Application data
    ~/.cache/taskweaver/               - Temporary cache
    ~/.local/state/taskweaver/         - Logs and history
"""

import os
import sys
import tomllib
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel, Field


def get_project_root() -> Path | None:
    """Detect project root directory.

    Searches for project markers (pyproject.toml, .git) starting from current directory.

    Returns:
        Path to project root if found, None otherwise.
    """
    current = Path.cwd()

    # Search up to 5 levels
    for _ in range(5):
        # Check for project markers
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current

        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    return None


def get_xdg_config_home() -> Path:
    """Get XDG config directory.

    Returns:
        Path to config directory (default: ~/.config).
    """
    return Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))


def get_xdg_data_home() -> Path:
    """Get XDG data directory.

    Returns:
        Path to data directory (default: ~/.local/share).
    """
    return Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def get_xdg_cache_home() -> Path:
    """Get XDG cache directory.

    Returns:
        Path to cache directory (default: ~/.cache).
    """
    return Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))


def get_xdg_state_home() -> Path:
    """Get XDG state directory.

    Returns:
        Path to state directory (default: ~/.local/state).
    """
    return Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state"))


class XDGPaths:
    """XDG-compliant paths for TaskWeaver with project-local support.

    Supports both project-local and system-wide XDG paths.
    Project-local files take precedence when they exist.
    """

    def __init__(self) -> None:
        """Initialize XDG paths."""
        self._project_root = get_project_root()
        self._config_dir = get_xdg_config_home() / "taskweaver"
        self._data_dir = get_xdg_data_home() / "taskweaver"
        self._cache_dir = get_xdg_cache_home() / "taskweaver"
        self._state_dir = get_xdg_state_home() / "taskweaver"

    @property
    def project_root(self) -> Path | None:
        """Project root directory if detected."""
        return self._project_root

    @property
    def config_dir(self) -> Path:
        """Config directory path (creates if missing)."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        return self._config_dir

    @property
    def data_dir(self) -> Path:
        """Data directory path (creates if missing)."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        return self._data_dir

    @property
    def cache_dir(self) -> Path:
        """Cache directory path (creates if missing)."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        return self._cache_dir

    @property
    def state_dir(self) -> Path:
        """State directory path (creates if missing)."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        return self._state_dir

    @property
    def config_file(self) -> Path:
        """Path to config.toml (project-local if exists, else XDG)."""
        if self._project_root:
            local_config = self._project_root / "config.toml"
            if local_config.exists():
                return local_config
        return self.config_dir / "config.toml"

    @property
    def env_file(self) -> Path:
        """Path to .env (project-local if exists, else XDG)."""
        if self._project_root:
            local_env = self._project_root / ".env"
            if local_env.exists():
                return local_env
        return self.config_dir / ".env"

    @property
    def database_file(self) -> Path:
        """Path to SQLite database (project-local if exists, else XDG)."""
        if self._project_root:
            local_db = self._project_root / "tasks.db"
            if local_db.exists():
                return local_db
        return self.data_dir / "tasks.db"

    @property
    def log_file(self) -> Path:
        """Path to application log."""
        return self.state_dir / "taskweaver.log"


def _load_env_file() -> None:
    """Load .env file with project-local precedence.

    Loads from:
    1. ./.env (project-local) if exists
    2. ~/.config/taskweaver/.env (XDG) if exists

    Called once during module import.
    """
    paths = XDGPaths()

    # Try project-local .env first
    if paths.project_root:
        local_env = paths.project_root / ".env"
        if local_env.exists():
            load_dotenv(local_env, override=True)
            return

    # Fall back to XDG .env
    xdg_env = paths.config_dir / ".env"
    if xdg_env.exists():
        load_dotenv(xdg_env, override=True)


class Config(BaseModel):
    """Application configuration.

    Simple, flat configuration structure with sensible defaults.
    Supports any LLM API endpoint (OpenAI, Anthropic, local models, etc.).
    """

    model: str = Field(
        default="gpt-4o-mini",
        description="LLM model name (e.g., gpt-4o-mini, claude-3-5-sonnet-20241022)",
    )
    api_endpoint: str = Field(
        default="https://api.openai.com/v1",
        description="API endpoint URL (OpenAI, Anthropic, local, or custom)",
    )
    auto_decompose: bool = Field(
        default=True,
        description="Automatically decompose complex tasks into subtasks",
    )
    log_level: str = Field(
        default="WARNING",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )


@lru_cache
def get_paths() -> XDGPaths:
    """Get cached XDG paths instance.

    Returns:
        Cached XDGPaths instance.

    Example:
        >>> from taskweaver.config import get_paths
        >>> paths = get_paths()
        >>> print(paths.database_file)
        PosixPath('/home/user/.local/share/taskweaver/tasks.db')
    """
    return XDGPaths()


@lru_cache
def get_config() -> Config:
    """Get cached configuration instance.

    Loads configuration with precedence hierarchy:
        1. Defaults (built-in)
        2. XDG user config (~/.config/taskweaver/config.toml)
        3. Project-local config (./config.toml) - overrides above

    Returns:
        Cached Config instance with merged preferences.

    Example:
        >>> from taskweaver.config import get_config
        >>> config = get_config()
        >>> print(config.model)
        'gpt-4o-mini'
    """
    paths = get_paths()

    # Start with defaults
    config_data: dict = {}

    # Load XDG config if it exists
    xdg_config = paths.config_dir / "config.toml"
    if xdg_config.exists():
        with xdg_config.open("rb") as f:
            config_data = tomllib.load(f)

    # Load project-local config if it exists (overrides XDG)
    if paths.project_root:
        local_config = paths.project_root / "config.toml"
        if local_config.exists():
            with local_config.open("rb") as f:
                local_data = tomllib.load(f)
                # Merge: local overrides XDG (flat structure)
                config_data.update(local_data)

    if not config_data:
        return Config()

    return Config(**config_data)


# Load .env file when module is imported
_load_env_file()

# Configure logging level from config
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    level=os.getenv("LOGURU_LEVEL", "WARNING"),
)
