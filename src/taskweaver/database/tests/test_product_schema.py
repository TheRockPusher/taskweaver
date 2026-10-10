"""Behavioral coverage for durable product data and atomic graph mutations."""

import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from taskweaver.config import Config
from taskweaver.database import connection, priority_service, repository
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import get_connection, init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.exceptions import DependencyError, TaskNotFoundError
from taskweaver.database.models import CompletionCreate, CompletionStatus, Task, TaskCreate, TaskStatus, TaskUpdate
from taskweaver.database.repository import TaskRepository
from taskweaver.database.schema import INSERT_TASK, SCHEMA_VERSION

if TYPE_CHECKING:
    from mem0 import Memory

_LEGACY_TASKS = """
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
    status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    duration_min INTEGER NOT NULL, llm_value REAL NOT NULL, requirement TEXT NOT NULL
)
"""
_LEGACY_DEPENDENCIES = """
CREATE TABLE task_dependencies (
    dependency_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, blocker_id TEXT NOT NULL,
    created_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY(blocker_id) REFERENCES tasks(task_id) ON DELETE CASCADE, UNIQUE(task_id,blocker_id)
)
"""
_LEGACY_COMPLETIONS = """
CREATE TABLE completion (
    completion_id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE REFERENCES tasks(task_id),
    status TEXT NOT NULL, closed_at TEXT NOT NULL, duration_expected INTEGER NOT NULL,
    duration_actual INTEGER NOT NULL, conclusion TEXT, created_at TEXT NOT NULL
)
"""
_STAMP = "2025-01-01T12:00:00+00:00"


def _task(repo: TaskRepository, title: str = "Task", **fields) -> UUID:
    return repo.create_task(
        TaskCreate(title=title, duration_min=30, llm_value=60, requirement="Delivered", **fields)
    ).task_id


def _stored(repo: TaskRepository, task_id: UUID) -> Task:
    task = repo.get_task(task_id)
    assert task is not None
    return task


@pytest.mark.parametrize("version", [None, 1, 4])
def test_legacy_migration_preserves_tasks_and_completion_history(tmp_path: Path, version: int | None) -> None:
    db_path = tmp_path / "legacy.db"
    ids = [uuid4() for _ in range(3)]
    completion_id = uuid4()
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(_LEGACY_TASKS)
        conn.executemany(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (str(task_id), title, "Original", status, _STAMP, _STAMP, 30, 60, "Delivered")
                for task_id, title, status in zip(
                    ids, ("Blocker", "Dependent", "Closed"), ("pending", "in_progress", "completed"), strict=True
                )
            ],
        )
        if version is not None:
            conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            conn.execute("INSERT INTO schema_version VALUES (?, ?)", (version, _STAMP))
        if version == 4:
            conn.execute(_LEGACY_DEPENDENCIES)
            conn.executemany(
                "INSERT INTO task_dependencies VALUES (?, ?, ?, ?)",
                [
                    (str(uuid4()), str(ids[1]), str(ids[0]), _STAMP),
                    (str(uuid4()), str(ids[1]), str(ids[2]), _STAMP),
                    (str(uuid4()), str(ids[1]), str(uuid4()), _STAMP),
                ],
            )
            conn.execute(_LEGACY_COMPLETIONS)
            conn.execute(
                "INSERT INTO completion VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(completion_id), str(ids[2]), "completed", _STAMP, 25, 40, "Kept", _STAMP),
            )
            conn.execute("CREATE VIEW tasks_full AS SELECT * FROM tasks")

    init_database(db_path)
    init_database(db_path)
    repo = TaskRepository(db_path)
    tasks = {task.task_id: task for task in repo.list_tasks()}
    assert set(tasks) == set(ids)
    assert tasks[ids[0]].title == "Blocker"
    assert tasks[ids[1]].status == TaskStatus.IN_PROGRESS
    assert tasks[ids[2]].status == TaskStatus.COMPLETED
    assert all(task.duration_min == task.raw_duration_min == 30 for task in tasks.values())
    assert all(
        (task.urgency, task.importance, task.effort, task.category) == (3, 3, 3, "general") for task in tasks.values()
    )
    with get_connection(db_path) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    if version == 4:
        assert [task.task_id for task in TaskDependencyRepository(db_path).get_blockers(ids[1])] == [ids[0]]
        completion = CompletionRepository(db_path).get_completion(completion_id)
        assert completion is not None
        assert (completion.duration_expected, completion.duration_actual, completion.conclusion) == (25, 40, "Kept")
        assert completion.raw_duration_min == 25
        assert completion.category == "general"
        assert completion.priority_factors is None
        repo.delete_task(ids[2])
        assert CompletionRepository(db_path).get_completion(completion_id) is None


def test_existing_legacy_file_auto_migrates_on_first_access(tmp_path: Path) -> None:
    db_path = tmp_path / "existing.db"
    task_id = uuid4()
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(_LEGACY_TASKS)
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(task_id), "Original", None, "pending", _STAMP, _STAMP, 20, 50, "Delivered"),
        )
    task = TaskRepository(db_path).get_task(task_id)
    assert task is not None
    assert task.raw_duration_min == 20
    assert task.category == "general"


def test_future_schema_is_rejected_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "future.db"
    future_version = SCHEMA_VERSION + 1
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_version VALUES (?, ?)", (future_version, _STAMP))
    with pytest.raises(ValueError, match="newer than supported"):
        init_database(db_path)
    with pytest.raises(ValueError, match="newer than supported"), get_connection(db_path):
        pass
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT version FROM schema_version").fetchall() == [(future_version,)]
        assert conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall() == [("schema_version",)]


def test_failed_migration_rolls_back_original_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "broken.db"
    task_id = uuid4()
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(_LEGACY_TASKS)
        conn.execute(_LEGACY_COMPLETIONS)
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_version VALUES (4, ?)", (_STAMP,))
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(task_id), "Preserved", None, "completed", _STAMP, _STAMP, 20, 50, "Delivered"),
        )
        conn.execute(
            "INSERT INTO completion VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid4()), str(task_id), "completed", _STAMP, 0, 10, None, _STAMP),
        )
    with pytest.raises(sqlite3.IntegrityError):
        init_database(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT title FROM tasks").fetchone()[0] == "Preserved"
        assert "raw_duration_min" not in {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 4
        assert conn.execute("SELECT duration_expected FROM completion").fetchone()[0] == 0


def test_new_fields_round_trip_and_nullable_fields_clear(task_repo: TaskRepository, temp_db: Path) -> None:
    goal_id = uuid4()
    with get_connection(temp_db) as conn, conn:
        conn.execute("INSERT INTO goals VALUES (?, ?, ?, ?, ?)", (str(goal_id), "Outcome", None, _STAMP, _STAMP))
    task_id = _task(
        task_repo,
        urgency=5,
        importance=4,
        effort=2,
        category="coding",
        goal_id=goal_id,
        skill_domain="python",
        required_skill_level=4,
        description="Notes",
        raw_duration_min=25,
    )
    task = task_repo.get_task(task_id)
    assert task is not None
    assert (task.urgency, task.importance, task.effort, task.category) == (5, 4, 2, "coding")
    assert (task.goal_id, task.skill_domain, task.required_skill_level) == (goal_id, "python", 4)
    assert task.priority_score is not None
    assert task.priority_updated_at is not None
    unchanged = task_repo.update_task(task_id, TaskUpdate(title="Renamed"))
    assert unchanged.description == "Notes"
    cleared = task_repo.update_task(
        task_id,
        TaskUpdate(description=None, goal_id=None, skill_domain=None, required_skill_level=None, duration_min=15),
    )
    assert (cleared.description, cleared.goal_id, cleared.skill_domain, cleared.required_skill_level) == (None,) * 4
    assert cleared.duration_min == 15
    assert cleared.raw_duration_min == 25
    assert task_repo.get_task(task_id) == cleared
    task_repo.mark_completed(task_id)
    cleared_score = task_repo.update_task(task_id, TaskUpdate(priority_score=None, priority_updated_at=None))
    assert cleared_score.priority_score is None
    assert cleared_score.priority_updated_at is None


@pytest.mark.parametrize("field", ["urgency", "importance", "effort", "required_skill_level"])
@pytest.mark.parametrize("score", [0, 6])
def test_score_bounds_are_rejected(field: str, score: int) -> None:
    with pytest.raises(ValidationError):
        TaskUpdate.model_validate({field: score})


def test_foreign_keys_are_enabled_on_every_connection(temp_db: Path) -> None:
    with get_connection(temp_db) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        conn.execute("PRAGMA foreign_keys = OFF")
    with get_connection(temp_db) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO task_dependencies VALUES (?, ?, ?, ?)", (str(uuid4()), str(uuid4()), str(uuid4()), _STAMP)
            )


@pytest.mark.parametrize("status", [TaskStatus.COMPLETED, TaskStatus.CANCELLED])
def test_terminal_blockers_release_edges_permanently(
    task_repo: TaskRepository, dep_repo: TaskDependencyRepository, temp_db: Path, status: TaskStatus
) -> None:
    blocker, downstream = _task(task_repo, "Blocker"), _task(task_repo, "Downstream")
    dep_repo.add_dependency(downstream, blocker)
    task_repo.update_task(blocker, TaskUpdate(status=status))
    assert dep_repo.get_blockers(downstream) == []
    with get_connection(temp_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM task_dependencies").fetchone()[0] == 0
    task_repo.update_task(blocker, TaskUpdate(status=TaskStatus.PENDING))
    assert dep_repo.get_blockers(downstream) == []
    assert next(task for task in task_repo.list_tasks_with_deps() if task.task_id == blocker).tasks_blocked_count == 0


def test_cleanup_failure_rolls_back_status_and_edges(
    task_repo: TaskRepository, dep_repo: TaskDependencyRepository, temp_db: Path
) -> None:
    blocker, downstream = _task(task_repo, "Blocker"), _task(task_repo, "Downstream")
    dep_repo.add_dependency(downstream, blocker)
    with get_connection(temp_db) as conn, conn:
        conn.execute("""CREATE TRIGGER reject_cleanup BEFORE DELETE ON task_dependencies
                     BEGIN SELECT RAISE(ABORT, 'cleanup refused'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="cleanup refused"):
        task_repo.mark_completed(blocker)
    assert _stored(task_repo, blocker).status == TaskStatus.PENDING
    assert [task.task_id for task in dep_repo.get_blockers(downstream)] == [blocker]


def test_ranking_failure_rolls_back_task_mutation(
    task_repo: TaskRepository, dep_repo: TaskDependencyRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocker, downstream = _task(task_repo, "Blocker"), _task(task_repo, "Downstream")
    dep_repo.add_dependency(downstream, blocker)

    def fail_refresh(_conn: sqlite3.Connection) -> int:
        raise RuntimeError("ranking refused")

    monkeypatch.setattr(repository, "refresh_priorities", fail_refresh)
    with pytest.raises(RuntimeError, match="ranking refused"):
        task_repo.mark_completed(blocker)
    assert _stored(task_repo, blocker).status == TaskStatus.PENDING
    assert [task.task_id for task in dep_repo.get_blockers(downstream)] == [blocker]


def test_terminal_downstream_does_not_inflate_counts_or_cd3(
    task_repo: TaskRepository, dep_repo: TaskDependencyRepository
) -> None:
    blocker = _task(task_repo, "Blocker")
    downstream = task_repo.create_task(
        TaskCreate(title="High CD3", duration_min=1, llm_value=100, requirement="Delivered")
    ).task_id
    dep_repo.add_dependency(downstream, blocker)
    assert dep_repo.calculate_effective_priorities()[blocker] == 100
    task_repo.mark_completed(downstream)
    assert dep_repo.get_blocked(blocker) == []
    enriched = next(task for task in task_repo.list_tasks_with_deps() if task.task_id == blocker)
    assert enriched.tasks_blocked_count == 0
    assert dep_repo.calculate_effective_priorities()[blocker] == enriched.priority


def test_duplicate_and_missing_blocker_report_domain_errors(
    task_repo: TaskRepository, dep_repo: TaskDependencyRepository
) -> None:
    blocker, downstream = _task(task_repo, "Blocker"), _task(task_repo, "Downstream")
    dep_repo.add_dependency(downstream, blocker)
    with pytest.raises(DependencyError):
        dep_repo.add_dependency(downstream, blocker)
    missing = uuid4()
    with pytest.raises(TaskNotFoundError, match=f"^Task not found: {missing}$"):
        dep_repo.add_dependency(downstream, missing)
    assert [task.task_id for task in dep_repo.get_blockers(downstream)] == [blocker]


def test_cd3_inheritance_handles_deep_chains_and_reports_corrupt_cycles(
    dep_repo: TaskDependencyRepository, temp_db: Path
) -> None:
    tasks = [Task(title=f"Task {index}", duration_min=1, llm_value=1, requirement="Delivered") for index in range(1300)]
    tasks[-1].llm_value = 100
    with get_connection(temp_db) as conn, conn:
        conn.executemany(INSERT_TASK, [task.model_dump(mode="json") for task in tasks])
        conn.executemany(
            "INSERT INTO task_dependencies VALUES (?, ?, ?, ?)",
            [
                (str(uuid4()), str(downstream.task_id), str(blocker.task_id), _STAMP)
                for blocker, downstream in pairwise(tasks)
            ],
        )
    priorities = dep_repo.calculate_effective_priorities()
    assert len(priorities) == len(tasks)
    assert set(priorities.values()) == {100}
    with get_connection(temp_db) as conn, conn:
        conn.execute(
            "INSERT INTO task_dependencies VALUES (?, ?, ?, ?)",
            (str(uuid4()), str(tasks[0].task_id), str(tasks[-1].task_id), _STAMP),
        )
    with pytest.raises(DependencyError, match="cycle"):
        dep_repo.calculate_effective_priorities()


def test_status_filtered_cd3_still_inherits_other_active_statuses(
    task_repo: TaskRepository, dep_repo: TaskDependencyRepository
) -> None:
    blocker = _task(task_repo, "Blocker")
    downstream = task_repo.create_task(
        TaskCreate(title="Pending downstream", duration_min=1, llm_value=100, requirement="Delivered")
    ).task_id
    task_repo.mark_in_progress(blocker)
    dep_repo.add_dependency(downstream, blocker)
    ranked = dep_repo.list_tasks_with_priority(TaskStatus.IN_PROGRESS)
    assert [task.task_id for task in ranked] == [blocker]
    assert ranked[0].effective_priority == 100


def test_task_removal_cascades_completion_edges_and_history(
    task_repo: TaskRepository, dep_repo: TaskDependencyRepository, completion_repo: CompletionRepository, temp_db: Path
) -> None:
    blocker, downstream = _task(task_repo, "Blocker"), _task(task_repo, "Downstream")
    dep_repo.add_dependency(downstream, blocker)
    completion = completion_repo.create_completion(
        CompletionCreate(
            task_id=downstream, status=CompletionStatus.COMPLETED, duration_expected=30, duration_actual=45
        )
    )
    task_repo.delete_task(downstream)
    assert completion_repo.get_completion(completion.completion_id) is None
    assert task_repo.get_task(downstream) is None
    with get_connection(temp_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM task_dependencies").fetchone()[0] == 0
        assert (
            conn.execute("SELECT COUNT(*) FROM priority_history WHERE task_id = ?", (str(downstream),)).fetchone()[0]
            == 0
        )
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_mcda_scores_refresh_after_every_task_and_dependency_mutation(
    task_repo: TaskRepository, dep_repo: TaskDependencyRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(priority_service, "_now", lambda: datetime(2025, 1, 1, tzinfo=UTC))
    blocker = _task(task_repo, "Blocker", urgency=1, importance=1, effort=5)
    downstream = _task(task_repo, "Downstream", urgency=5, importance=5, effort=1)
    assert _stored(task_repo, blocker).priority_score == 0
    assert _stored(task_repo, downstream).priority_score == 80
    assert [task.task_id for task in task_repo.list_tasks_by_priority(limit=1)] == [downstream]
    dep_repo.add_dependency(downstream, blocker)
    assert _stored(task_repo, blocker).priority_score == 1
    dep_repo.remove_dependency(downstream, blocker)
    assert _stored(task_repo, blocker).priority_score == 0
    updated = task_repo.update_task_scores(blocker, urgency=5)
    assert updated.priority_score == 30
    assert updated.importance == 1
    dep_repo.add_dependency(downstream, blocker)
    task_repo.mark_cancelled(downstream)
    assert _stored(task_repo, blocker).priority_score == 30
    task_repo.update_task(downstream, TaskUpdate(status=TaskStatus.PENDING))
    assert _stored(task_repo, blocker).priority_score == 31
    task_repo.delete_task(downstream)
    assert _stored(task_repo, blocker).priority_score == 30
    assert task_repo.list_tasks_by_priority(limit=0) == []
    assert [task.task_id for task in task_repo.list_tasks_by_priority(status=TaskStatus.PENDING)] == [blocker]
    with pytest.raises(ValueError, match="nonnegative"):
        task_repo.list_tasks_by_priority(limit=-1)


def test_sqlite_usage_does_not_initialize_semantic_backends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*_args, **_kwargs):
        raise AssertionError("Semantic backend was invoked during SQLite use")

    monkeypatch.setitem(sys.modules, "mem0", SimpleNamespace(Memory=unavailable))
    monkeypatch.setitem(sys.modules, "qdrant_client", SimpleNamespace(QdrantClient=unavailable))
    monkeypatch.setattr(connection, "DEFAULT_QDRANT_PATH", tmp_path / "vectors")
    repo = TaskRepository(tmp_path / "sqlite" / "tasks.db")
    task_id = _task(repo)
    assert repo.get_task(task_id) is not None
    assert not (tmp_path / "vectors").exists()


def test_semantic_client_closes_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class Client:
        def __init__(self, *, path: str) -> None:
            calls.append(path)

        def close(self) -> None:
            calls.append("closed")

    monkeypatch.setitem(sys.modules, "qdrant_client", SimpleNamespace(QdrantClient=Client))
    with pytest.raises(RuntimeError, match="consumer failed"), connection.get_qdrant_client(tmp_path / "vectors"):
        raise RuntimeError("consumer failed")
    assert calls == [str(tmp_path / "vectors"), "closed"]
    assert not (tmp_path / "tasks.db").exists()


@pytest.mark.parametrize("missing_key", ["OPENROUTER_API_KEY", "OPENAI_API_KEY"])
def test_missing_memory_key_is_actionable_before_backend_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_key: str
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-test-credential")
    monkeypatch.setenv("OPENAI_API_KEY", "embedding-test-credential")
    monkeypatch.delenv(missing_key)

    class Backend:
        @classmethod
        def from_config(cls, _config):
            raise AssertionError("Missing credentials must be caught before any backend creation")

    monkeypatch.setitem(sys.modules, "mem0", SimpleNamespace(Memory=Backend))
    monkeypatch.setattr(
        connection, "get_paths", lambda: SimpleNamespace(qdrant_dir=tmp_path / "vectors", data_dir=tmp_path)
    )
    with pytest.raises(RuntimeError, match=missing_key) as error:
        connection.mem0_memory(Config(mem0_llm_provider="openrouter"))
    assert "router-test-credential" not in str(error.value)
    assert "embedding-test-credential" not in str(error.value)
    assert not (tmp_path / "vectors").exists()


@pytest.mark.parametrize("has_history", [True, False])
@pytest.mark.parametrize("failed_client", ["vector", "telemetry", "both"])
def test_mem0_closes_all_resources_even_when_clients_fail(has_history: bool, failed_client: str) -> None:
    class Client:
        def __init__(self, *, fail: bool = False) -> None:
            self.closed = False
            self.fail = fail

        def close(self) -> None:
            self.closed = True
            if self.fail:
                raise RuntimeError("client close refused")

    vector = Client(fail=failed_client in {"vector", "both"})
    telemetry = Client(fail=failed_client in {"telemetry", "both"})
    history = sqlite3.connect(":memory:") if has_history else None
    memory = SimpleNamespace(
        vector_store=SimpleNamespace(client=vector),
        _telemetry_vector_store=SimpleNamespace(client=telemetry),
        db=SimpleNamespace(connection=history),
    )
    with pytest.raises(RuntimeError, match="client close refused"):
        connection.close_mem0_memory(cast("Memory", memory))
    assert vector.closed
    assert telemetry.closed
    if history is not None:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            history.execute("SELECT 1")
