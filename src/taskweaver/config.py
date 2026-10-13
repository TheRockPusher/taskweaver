"""Native application paths, project overrides, and TOML configuration."""

import os
import sys
import tomllib
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field


def get_project_root() -> Path | None:
    """Find an explicit TaskWeaver config, legacy database, or project marker."""
    current = Path.cwd()
    for directory in (current, *current.parents):
        if any((directory / name).exists() for name in ("config.toml", "tasks.db", "pyproject.toml", ".git")):
            return directory
    return None


def _native_home(kind: str) -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        directories = {
            "config": "Application Support",
            "data": "Application Support",
            "cache": "Caches",
            "state": "Logs",
        }
        return home / "Library" / directories[kind]
    if sys.platform == "win32":
        variable = "APPDATA" if kind == "config" else "LOCALAPPDATA"
        fallback = home / "AppData" / ("Roaming" if kind == "config" else "Local")
        return Path(os.environ.get(variable) or fallback)
    return home / {"config": ".config", "data": ".local/share", "cache": ".cache", "state": ".local/state"}[kind]


def get_xdg_config_home() -> Path:
    """Return the native config root, respecting an explicit XDG override."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or _native_home("config"))


def get_xdg_data_home() -> Path:
    """Return the native data root, respecting an explicit XDG override."""
    return Path(os.environ.get("XDG_DATA_HOME") or _native_home("data"))


def get_xdg_cache_home() -> Path:
    """Return the native cache root, respecting an explicit XDG override."""
    return Path(os.environ.get("XDG_CACHE_HOME") or _native_home("cache"))


def get_xdg_state_home() -> Path:
    """Return the native log/state root, respecting an explicit XDG override."""
    return Path(os.environ.get("XDG_STATE_HOME") or _native_home("state"))


class XDGPaths:
    """Native user paths with existing project-local files taking precedence."""

    def __init__(self) -> None:
        self._project_root = get_project_root()
        self._config_dir = get_xdg_config_home() / "taskweaver"
        self._data_dir = get_xdg_data_home() / "taskweaver"
        self._cache_dir = get_xdg_cache_home() / "taskweaver"
        self._state_dir = get_xdg_state_home() / "taskweaver"

    @property
    def project_root(self) -> Path | None:
        """Return the detected existing project directory, if any."""
        return self._project_root

    @staticmethod
    def _directory(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        return path

    @property
    def config_dir(self) -> Path:
        """Return and create the user configuration directory."""
        return self._directory(self._config_dir)

    @property
    def data_dir(self) -> Path:
        """Return and create the user data directory."""
        return self._directory(self._data_dir)

    @property
    def cache_dir(self) -> Path:
        """Return and create the user cache directory."""
        return self._directory(self._cache_dir)

    @property
    def state_dir(self) -> Path:
        """Return and create the user log/state directory."""
        return self._directory(self._state_dir)

    def _local_or_user(self, name: str) -> Path:
        if self.project_root:
            local = self.project_root / name
            if local.is_file():
                return local
        return self.config_dir / name

    @property
    def config_file(self) -> Path:
        """Prefer an existing project config over the user configuration file."""
        return self._local_or_user("config.toml")

    @property
    def env_file(self) -> Path:
        """Prefer an existing project env file over the user secrets file."""
        return self._local_or_user(".env")

    @property
    def database_file(self) -> Path:
        """Resolve an explicit override, an existing legacy DB, or native user data."""
        configured = get_config().database_file
        if configured is not None:
            configured.parent.mkdir(parents=True, exist_ok=True)
            return configured
        if self.project_root:
            legacy = self.project_root / "tasks.db"
            if legacy.is_file():
                return legacy
        return self.data_dir / "tasks.db"

    @property
    def qdrant_dir(self) -> Path:
        """Place optional semantic storage beside the selected database."""
        return self.database_file.parent / "qdrant_store"

    @property
    def log_file(self) -> Path:
        """Return the application log path in the native log/state directory."""
        return self.state_dir / "taskweaver.log"


_loaded_env: dict[str, str] = {}


def _load_env_file() -> None:
    """Merge user and local secrets without replacing explicit process variables."""
    paths = get_paths()
    files = [paths.config_dir / ".env"]
    if paths.project_root:
        files.append(paths.project_root / ".env")
    values: dict[str, str] = {}
    for file in files:
        if file.is_file():
            values.update(
                {key: value for key, value in dotenv_values(file, interpolate=False).items() if value is not None}
            )
    for key, old_value in _loaded_env.items():
        if key not in values and os.environ.get(key) == old_value:
            os.environ.pop(key, None)
    loaded: dict[str, str] = {}
    for key, value in values.items():
        if key not in os.environ or os.environ[key] == _loaded_env.get(key):
            os.environ[key] = value
            loaded[key] = value
    _loaded_env.clear()
    _loaded_env.update(loaded)


class Config(BaseModel):
    """Flat user preferences; provider credentials live only in the environment."""

    llm_model: str = "openai:gpt-4o-mini"
    api_endpoint: str | None = None
    database_file: Path | None = None
    user_id: str = "default"
    github_repos: list[str] = Field(default_factory=list)
    github_sync_interval_seconds: int = Field(default=3600, ge=30)
    memory_enabled: bool = False
    mem0_llm_provider: str = "openai"
    mem0_llm_model: str | None = None
    mem0_embedding: str = "text-embedding-3-small"
    mem0_embedding_provider: str = "openai"
    mem0_embedding_endpoint: str | None = None
    mem0_site_url: str | None = None
    mem0_max_memories: int = Field(default=10, ge=1, le=100)

    @property
    def mem0_llm_provider_resolved(self) -> str:
        """Translate gateway/local/Google names to their Mem0 SDK providers."""
        if self.mem0_llm_provider in {"google", "google-genai"}:
            return "gemini"
        return "openai" if self.mem0_llm_provider in {"openrouter", "local"} else self.mem0_llm_provider

    @property
    def mem0_site_url_resolved(self) -> str | None:
        """Resolve an explicit LLM endpoint or OpenRouter's native gateway URL."""
        if self.mem0_llm_provider == "openrouter":
            return self.mem0_site_url or "https://openrouter.ai/api/v1"
        return self.mem0_site_url


@lru_cache
def get_paths() -> XDGPaths:
    """Return the cached native path resolver."""
    return XDGPaths()


@lru_cache
def get_config() -> Config:
    """Load defaults, user config, then project config; anchor relative DB paths."""
    paths = get_paths()
    _load_env_file()
    files = [paths.config_dir / "config.toml"]
    if paths.project_root:
        files.append(paths.project_root / "config.toml")
    data: dict = {}
    for file in files:
        if file.is_file():
            try:
                with file.open("rb") as stream:
                    values = tomllib.load(stream)
            except tomllib.TOMLDecodeError as exc:
                raise ValueError(f"Invalid configuration in {file}: {exc}") from exc
            if "database_file" in values:
                if not isinstance(values["database_file"], str) or not values["database_file"].strip():
                    raise ValueError(f"Invalid configuration in {file}: database_file must be a nonempty path string")
                database = Path(values["database_file"]).expanduser()
                values["database_file"] = database if database.is_absolute() else (file.parent / database).resolve()
            data.update(values)
    return Config(**data)
