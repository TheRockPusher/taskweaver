"""Transactional SQLite initialization and lazy semantic-backend connections."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Generator
from contextlib import ExitStack, closing, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from ..config import Config, get_paths
from .schema import (
    CREATE_COMPLETION,
    CREATE_DEPENDENCY_TABLE,
    CREATE_GOALS_TABLE,
    CREATE_SCHEMA_VERSION_TABLE,
    CREATE_TASKS_TABLE,
    INSERT_SCHEMA_VERSION,
    SCHEMA_STATEMENTS,
    SCHEMA_VERSION,
    TASK_COLUMNS,
)

if TYPE_CHECKING:
    from mem0 import Memory
    from qdrant_client import QdrantClient


# Version 5 introduced the current task-table layout; later additive migrations
# must not rebuild those tables or disturb their foreign keys and history.
_TASK_LAYOUT_SCHEMA_VERSION = 5

_TASK_DEFAULTS = {
    "description": "NULL",
    "raw_duration_min": "duration_min",
    "urgency": "3",
    "importance": "3",
    "effort": "3",
    "category": "'general'",
    "goal_id": "NULL",
    "skill_domain": "NULL",
    "required_skill_level": "NULL",
    "priority_score": "NULL",
    "priority_updated_at": "NULL",
}

_MEMORY_KEY_NAMES = {
    "openai": "OPENAI_API_KEY",
    "openai_structured": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "azure_openai_structured": "AZURE_OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "xai": "XAI_API_KEY",
    "sarvam": "SARVAM_API_KEY",
}
_MEMORY_EXTERNAL_AUTH_PROVIDERS = frozenset(
    {
        "ollama",
        "huggingface",
        "lmstudio",
        "vllm",
        "vertexai",
        "aws_bedrock",
        "langchain",
        "litellm",
    }
)
_MEMORY_MODEL_PREFIXES = (
    frozenset(_MEMORY_KEY_NAMES) | _MEMORY_EXTERNAL_AUTH_PROVIDERS | {"google", "google-genai", "local"}
)


def get_database_path() -> Path:
    """Resolve the selected database only when an operation requests it."""
    return get_paths().database_file


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None
    )


def _schema_version(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "schema_version"):
        return 0
    return conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]


def _migrate_tasks(conn: sqlite3.Connection) -> None:
    """Rebuild legacy tables without disabling foreign-key enforcement."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    missing = set(TASK_COLUMNS) - columns - _TASK_DEFAULTS.keys()
    if missing:
        msg = f"Unsupported legacy tasks schema; missing columns: {', '.join(sorted(missing))}"
        raise ValueError(msg)
    conn.execute("ALTER TABLE tasks RENAME TO tasks_legacy")
    conn.execute(CREATE_TASKS_TABLE)
    projection = ", ".join(column if column in columns else _TASK_DEFAULTS[column] for column in TASK_COLUMNS)
    # Both identifiers and expressions come exclusively from the schema constants above.
    conn.execute(
        "INSERT INTO tasks (" + ", ".join(TASK_COLUMNS) + ") SELECT " + projection + " FROM tasks_legacy"  # noqa: S608
    )
    _migrate_dependencies(conn)
    _migrate_completions(conn)
    conn.execute("DROP TABLE tasks_legacy")


def _migrate_dependencies(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "task_dependencies"):
        return
    conn.execute("ALTER TABLE task_dependencies RENAME TO task_dependencies_legacy")
    conn.execute(CREATE_DEPENDENCY_TABLE)
    conn.execute(
        """INSERT INTO task_dependencies (dependency_id, task_id, blocker_id, created_at)
        SELECT d.dependency_id, d.task_id, d.blocker_id, d.created_at
        FROM task_dependencies_legacy d
        JOIN tasks downstream ON downstream.task_id = d.task_id
        JOIN tasks blocker ON blocker.task_id = d.blocker_id
        WHERE blocker.status IN ('pending', 'in_progress')"""
    )
    conn.execute("DROP TABLE task_dependencies_legacy")


def _migrate_completions(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "completion"):
        return
    columns = {row[1] for row in conn.execute("PRAGMA table_info(completion)")}
    conn.execute("ALTER TABLE completion RENAME TO completion_legacy")
    conn.execute(CREATE_COMPLETION)
    baseline = (
        "COALESCE(c.raw_duration_min, c.duration_expected)" if "raw_duration_min" in columns else "c.duration_expected"
    )
    category = "COALESCE(c.category, t.category)" if "category" in columns else "t.category"
    factors = "c.priority_factors" if "priority_factors" in columns else "NULL"
    # These three expressions are selected from fixed SQL strings, never user input.
    conn.execute(
        """INSERT INTO completion (
            completion_id, task_id, status, closed_at, duration_expected, duration_actual,
            conclusion, created_at, raw_duration_min, category, priority_factors
        ) SELECT c.completion_id, c.task_id, c.status, c.closed_at, c.duration_expected,
            c.duration_actual, c.conclusion, c.created_at, """  # noqa: S608
        + baseline
        + ", "
        + category
        + ", "
        + factors
        + " FROM completion_legacy c JOIN tasks t ON t.task_id = c.task_id"
    )
    conn.execute("DROP TABLE completion_legacy")


def init_database(db_path: Path | None = None) -> None:
    """Create or migrate SQLite atomically, preserving valid legacy records.

    Args:
        db_path: Path to SQLite database file.

    Raises:
        ValueError: If the database is newer than supported or has an unknown legacy shape.
    """
    db_path = db_path if db_path is not None else get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            version = _schema_version(conn)
            if version > SCHEMA_VERSION:
                msg = f"Database schema version {version} is newer than supported version {SCHEMA_VERSION}"
                raise ValueError(msg)
            conn.execute(CREATE_SCHEMA_VERSION_TABLE)
            conn.execute(CREATE_GOALS_TABLE)
            if version < _TASK_LAYOUT_SCHEMA_VERSION and _table_exists(conn, "tasks"):
                conn.execute("DROP VIEW IF EXISTS tasks_full")
                _migrate_tasks(conn)
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
            conn.execute(INSERT_SCHEMA_VERSION, (SCHEMA_VERSION,))
    logger.debug(f"SQLite ready at {db_path} (schema {SCHEMA_VERSION})")


@contextmanager
def get_connection(db_path: Path | None = None) -> Generator[sqlite3.Connection]:
    """Open SQLite with foreign keys enabled, initializing or migrating as needed.

    Args:
        db_path: Path to SQLite database file.

    Yields:
        Connection with named-row access; callers own transaction boundaries.
    """
    db_path = db_path if db_path is not None else get_database_path()
    if not db_path.exists():
        init_database(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        version = _schema_version(conn)
        if version > SCHEMA_VERSION:
            msg = f"Database schema version {version} is newer than supported version {SCHEMA_VERSION}"
            raise ValueError(msg)
        if version < SCHEMA_VERSION:
            init_database(db_path)
        conn.row_factory = sqlite3.Row
        yield conn


@contextmanager
def get_qdrant_client(qdrant_path: Path | None = None) -> Generator[QdrantClient]:
    """Open a semantic backend only when requested, closing it on every exit.

    Args:
        qdrant_path: Directory for Qdrant storage, independent of SQLite.

    Yields:
        A local Qdrant client.
    """
    # Keep the optional semantic backend unavailable until explicitly requested.
    from qdrant_client import QdrantClient  # noqa: PLC0415

    qdrant_path = qdrant_path if qdrant_path is not None else get_paths().qdrant_dir
    qdrant_path.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(qdrant_path))
    try:
        yield client
    finally:
        client.close()


def _memory_provider_key(provider: str, role: str) -> str | None:
    if provider in _MEMORY_EXTERNAL_AUTH_PROVIDERS:
        return None
    key_name = _MEMORY_KEY_NAMES.get(provider, f"{provider.upper()}_API_KEY")
    key = os.getenv(key_name)
    if not key or not key.strip():
        msg = f"Mem0 {role} provider '{provider}' requires {key_name}. Set it or disable semantic memory."
        raise RuntimeError(msg)
    return key


def _memory_role(
    provider: str, model: str, role: str, endpoint: str | None, *, resolve_prefix: bool = True
) -> tuple[str, dict[str, str]]:
    prefix, separator, model_name = model.partition(":")
    if separator and prefix in _MEMORY_MODEL_PREFIXES:
        model = model_name
        if resolve_prefix:
            provider = prefix
    if provider in {"google", "google-genai"}:
        provider = "gemini"
    if provider == "local":
        if not endpoint:
            msg = f"Mem0 local {role} requires its own explicit endpoint. Configure it or disable semantic memory."
            raise RuntimeError(msg)
        key = os.getenv("TASKWEAVER_API_KEY", "")
        provider = "openai"
    else:
        key = _memory_provider_key(provider, role)
        if provider == "openrouter":
            provider = "openai"
            endpoint = endpoint or "https://openrouter.ai/api/v1"
        elif provider == "openai":
            endpoint = endpoint or "https://api.openai.com/v1"
    config = {"model": model}
    if key is not None:
        config["api_key"] = key
    if endpoint:
        config["openai_base_url"] = endpoint
    return provider, config


def mem0_memory(toml_config: Config) -> Memory:
    """Initialize semantic memory lazily after validating provider credentials.

    Args:
        toml_config: Application configuration with Mem0 settings.

    Returns:
        Configured backend; its owner must call close_mem0_memory when finished.

    Raises:
        RuntimeError: If a configured API key or the optional memory extra is missing.
    """
    llm_provider, llm_config = _memory_role(
        toml_config.mem0_llm_provider,
        toml_config.mem0_llm_model or toml_config.llm_model,
        "LLM",
        toml_config.mem0_site_url,
        resolve_prefix=toml_config.mem0_llm_model is not None,
    )
    embedding_provider, embedding_config = _memory_role(
        toml_config.mem0_embedding_provider,
        toml_config.mem0_embedding,
        "embedding",
        toml_config.mem0_embedding_endpoint,
    )
    paths = get_paths()
    os.environ.setdefault("MEM0_DIR", str(paths.data_dir / "mem0"))
    # Explicit facts must not opt users into third-party analytics.
    os.environ.setdefault("MEM0_TELEMETRY", "False")
    try:
        # Core SQLite operation must not require the optional memory extra.
        from mem0 import Memory  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        msg = "Semantic memory requires the optional memory extra: install taskweaver[memory]."
        raise RuntimeError(msg) from exc
    from .mem0_openai import register_openai_providers  # noqa: PLC0415

    register_openai_providers()

    qdrant_path = toml_config.database_file.parent / "qdrant_store" if toml_config.database_file else paths.qdrant_dir
    qdrant_path.mkdir(parents=True, exist_ok=True)
    config = {
        "history_db_path": str(qdrant_path / "memory_history.db"),
        "vector_store": {
            "provider": "qdrant",
            "config": {"collection_name": "test", "path": str(qdrant_path), "on_disk": True},
        },
        "llm": {"provider": llm_provider, "config": llm_config},
        "embedder": {"provider": embedding_provider, "config": embedding_config},
    }
    return Memory.from_config(config)


def close_mem0_memory(memory: Memory) -> None:
    """Close owned Qdrant, optional telemetry, history, and model clients despite failures."""
    with ExitStack() as cleanup:
        history_connection = memory.db.connection
        if history_connection is not None:
            cleanup.callback(history_connection.close)
        telemetry_store = getattr(memory, "_telemetry_vector_store", None)
        if telemetry_store is not None:
            cleanup.callback(telemetry_store.client.close)
        cleanup.callback(memory.vector_store.client.close)
        for component in (getattr(memory, "llm", None), getattr(memory, "embedding_model", None)):
            client = getattr(component, "client", None)
            close = getattr(client, "close", None)
            if callable(close):
                cleanup.callback(close)
