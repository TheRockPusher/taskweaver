"""Batched MCDA scoring, actionable DAG ranking, and evidence-based preferences."""

import json
import math
import sqlite3
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .connection import get_connection, get_database_path
from .exceptions import DependencyError, TaskNotFoundError
from .models import Task, TaskStatus, TaskWithDependencies

FACTOR_NAMES = ("urgency", "importance", "effort", "dependencies", "age")
ACTIVE_STATUSES = (TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value)
DEPENDENCY_CAP = 10
AGE_CAP_DAYS = 30
LEARNING_MINIMUM = 20
LEARNING_RATE = 0.1


class PriorityWeights(BaseModel):
    """Finite nonnegative MCDA weights whose sum is one."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    urgency: float = Field(default=0.30, ge=0)
    importance: float = Field(default=0.35, ge=0)
    effort: float = Field(default=0.15, ge=0)
    dependencies: float = Field(default=0.10, ge=0)
    age: float = Field(default=0.10, ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        """Reject weights that would change the score's 0..100 scale."""
        if not math.isclose(sum(self.model_dump().values()), 1.0, rel_tol=0, abs_tol=1e-9):
            raise ValueError("Priority weights must sum to 1")
        return self


def _now() -> datetime:
    return datetime.now(UTC)


def _load_weights(conn: sqlite3.Connection) -> PriorityWeights:
    row = conn.execute("SELECT weights FROM priority_preferences WHERE singleton = 1").fetchone()
    return PriorityWeights.model_validate_json(row["weights"]) if row else PriorityWeights()


def _raw_factors(row: sqlite3.Row, dependencies: int, now: datetime) -> dict[str, float]:
    created_at = datetime.fromisoformat(row["created_at"])
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return {
        "urgency": float(row["urgency"]),
        "importance": float(row["importance"]),
        "effort": float(row["effort"]),
        "dependencies": float(dependencies),
        "age": (now - created_at).total_seconds() / 86400,
    }


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    return {
        "urgency": (raw["urgency"] - 1) / 4,
        "importance": (raw["importance"] - 1) / 4,
        "effort": (5 - raw["effort"]) / 4,
        "dependencies": min(DEPENDENCY_CAP, raw["dependencies"]) / DEPENDENCY_CAP,
        "age": min(AGE_CAP_DAYS, max(0, raw["age"])) / AGE_CAP_DAYS,
    }


def _score(factors: dict[str, float], weights: PriorityWeights) -> float:
    return round(min(100.0, max(0.0, 100 * sum(factors[name] * getattr(weights, name) for name in FACTOR_NAMES))), 1)


class _Snapshot:
    """One database read set shared by scoring, explanation, and ranking."""

    def __init__(self, conn: sqlite3.Connection, weights: PriorityWeights) -> None:
        self.rows = {row["task_id"]: row for row in conn.execute("SELECT * FROM tasks")}
        self.blockers: dict[str, list[str]] = {key: [] for key in self.rows}
        self.dependents: dict[str, list[str]] = {key: [] for key in self.rows}
        edges = conn.execute(
            "SELECT d.task_id, d.blocker_id FROM task_dependencies d "
            "JOIN tasks t ON t.task_id = d.task_id JOIN tasks b ON b.task_id = d.blocker_id "
            "WHERE t.status IN ('pending', 'in_progress') AND b.status IN ('pending', 'in_progress')"
        )
        for edge in edges:
            self.blockers[edge["task_id"]].append(edge["blocker_id"])
            self.dependents[edge["blocker_id"]].append(edge["task_id"])
        now = _now()
        self.raw = {key: _raw_factors(row, len(self.dependents[key]), now) for key, row in self.rows.items()}
        self.normalized = {key: _normalize(raw) for key, raw in self.raw.items()}
        self.scores = {key: _score(factors, weights) for key, factors in self.normalized.items()}

    def require(self, task_id: UUID) -> str:
        key = str(task_id)
        if key not in self.rows:
            raise TaskNotFoundError(task_id)
        return key

    def selected(self, status: TaskStatus | None) -> list[str]:
        statuses = (status.value,) if status is not None else ACTIVE_STATUSES
        return [key for key, row in self.rows.items() if row["status"] in statuses]

    def effective(self) -> dict[str, float]:
        scores = self.scores.copy()
        remaining = {key: len(tasks) for key, tasks in self.dependents.items()}
        queue = deque(key for key, count in remaining.items() if not count)
        processed = 0
        while queue:
            key = queue.popleft()
            processed += 1
            for blocker in self.blockers[key]:
                scores[blocker] = max(scores[blocker], scores[key])
                remaining[blocker] -= 1
                if not remaining[blocker]:
                    queue.append(blocker)
        if processed != len(self.rows):
            raise DependencyError("Cannot rank a cyclic task dependency graph")
        return scores


def completion_priority_factors(conn: sqlite3.Connection, task_id: UUID) -> dict[str, float]:
    """Snapshot normalized factors before closing a task, in the caller's transaction."""
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone()
    if row is None:
        raise TaskNotFoundError(task_id)
    count = conn.execute(
        "SELECT COUNT(*) FROM task_dependencies d JOIN tasks t ON t.task_id = d.task_id "
        "WHERE d.blocker_id = ? AND t.status IN ('pending', 'in_progress')",
        (str(task_id),),
    ).fetchone()[0]
    return _normalize(_raw_factors(row, count, _now()))


def _valid_snapshot(value: str | None) -> dict[str, float] | None:
    if value is None:
        return None
    try:
        factors = json.loads(value)
    except (ValueError, TypeError):
        return None
    if not isinstance(factors, dict) or set(factors) != set(FACTOR_NAMES):
        return None
    if any(
        isinstance(value, bool) or not isinstance(value, (float, int)) or not 0 <= value <= 1
        for value in factors.values()
    ):
        return None
    return factors


def _learn_preferences(conn: sqlite3.Connection) -> None:
    preference = conn.execute(
        "SELECT weights, source, sample_count FROM priority_preferences WHERE singleton = 1"
    ).fetchone()
    if preference and preference["source"] == "custom":
        return
    samples = [
        factors
        for row in conn.execute("SELECT priority_factors FROM completion WHERE status = 'completed'")
        if (factors := _valid_snapshot(row["priority_factors"])) is not None
    ]
    if len(samples) < LEARNING_MINIMUM:
        if preference:
            conn.execute("DELETE FROM priority_preferences WHERE singleton = 1")
        return
    # Recompute from current evidence, even at the same count; blend into defaults without cumulative drift.
    baseline = PriorityWeights().model_dump()
    evidence = {
        name: baseline[name] * (0.5 + math.fsum(sample[name] for sample in samples) / len(samples))
        for name in FACTOR_NAMES
    }
    total = sum(evidence.values())
    weights = PriorityWeights.model_validate(
        {name: (1 - LEARNING_RATE) * baseline[name] + LEARNING_RATE * evidence[name] / total for name in FACTOR_NAMES}
    )
    if (
        preference
        and preference["sample_count"] == len(samples)
        and PriorityWeights.model_validate_json(preference["weights"]) == weights
    ):
        return
    _save_weights(conn, weights, "learned", len(samples))


def _save_weights(conn: sqlite3.Connection, weights: PriorityWeights, source: str, sample_count: int) -> None:
    conn.execute(
        "INSERT INTO priority_preferences(singleton, weights, source, sample_count, updated_at) VALUES (1, ?, ?, ?, ?) "
        "ON CONFLICT(singleton) DO UPDATE SET weights=excluded.weights, source=excluded.source, "
        "sample_count=excluded.sample_count, updated_at=excluded.updated_at",
        (weights.model_dump_json(), source, sample_count, _now().isoformat()),
    )


def _persist(conn: sqlite3.Connection, snapshot: _Snapshot, keys: list[str]) -> int:
    changed = [key for key in keys if snapshot.rows[key]["priority_score"] != snapshot.scores[key]]
    if not changed:
        return 0
    timestamp = _now().isoformat()
    conn.executemany(
        "UPDATE tasks SET priority_score = ?, priority_updated_at = ? WHERE task_id = ?",
        [(snapshot.scores[key], timestamp, key) for key in changed],
    )
    conn.executemany(
        "INSERT INTO priority_history(task_id, score, recorded_at) VALUES (?, ?, ?)",
        [(key, snapshot.scores[key], timestamp) for key in changed],
    )
    return len(changed)


def refresh_priorities(conn: sqlite3.Connection) -> int:
    """Refresh changed active scores and learning atomically, restoring defaults below twenty samples."""
    _learn_preferences(conn)
    snapshot = _Snapshot(conn, _load_weights(conn))
    return _persist(conn, snapshot, snapshot.selected(None))


class PriorityService:
    """Calculate MCDA scores without reads causing history or preference side effects."""

    def __init__(self, db_path: Path | None = None, weights: PriorityWeights | None = None) -> None:
        self.db_path = db_path if db_path is not None else get_database_path()
        if weights is not None:
            self.adjust_weights(weights)

    @property
    def weights(self) -> PriorityWeights:
        """Return the latest persisted weights, including changes from other sessions."""
        with get_connection(self.db_path) as conn:
            return _load_weights(conn)

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        """List all matching tasks newest first with current, unpersisted MCDA scores.

        Unlike active priority calculations, an omitted status includes closed tasks.
        Scores and task fields share one read snapshot; listing never adds history.
        """
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            snapshot = _Snapshot(conn, _load_weights(conn))
        tasks = [
            Task.model_validate({**dict(row), "priority_score": snapshot.scores[key]})
            for key, row in snapshot.rows.items()
            if status is None or row["status"] == status.value
        ]
        tasks.sort(key=lambda task: task.created_at, reverse=True)
        return tasks

    def list_tasks_with_deps(self) -> list[TaskWithDependencies]:
        """List active tasks with current MCDA scores and counts from one read snapshot."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            snapshot = _Snapshot(conn, _load_weights(conn))
        tasks = [
            TaskWithDependencies.model_validate(
                {
                    **dict(snapshot.rows[key]),
                    "priority_score": snapshot.scores[key],
                    "tasks_blocked_count": len(snapshot.dependents[key]),
                    "active_blocker_count": len(snapshot.blockers[key]),
                }
            )
            for key in snapshot.selected(None)
        ]
        tasks.sort(key=lambda task: task.created_at, reverse=True)
        return tasks

    def calculate_priority(self, task_id: UUID) -> float:
        """Calculate a task's intrinsic score; never mutate its stored score."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            snapshot = _Snapshot(conn, _load_weights(conn))
        return snapshot.scores[snapshot.require(task_id)]

    def calculate_all_priorities(self, status: TaskStatus | None = None) -> dict[UUID, float]:
        """Calculate active scores in a fixed number of reads, or one explicit status."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            snapshot = _Snapshot(conn, _load_weights(conn))
        return {UUID(key): snapshot.scores[key] for key in snapshot.selected(status)}

    def calculate_effective_priorities(self, status: TaskStatus | None = None) -> dict[UUID, float]:
        """Propagate downstream active MCDA scores upstream in linear DAG order."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            snapshot = _Snapshot(conn, _load_weights(conn))
        effective = snapshot.effective()
        return {UUID(key): effective[key] for key in snapshot.selected(status)}

    def update_all_priorities(self, status: TaskStatus | None = None) -> int:
        """Persist selected scores; return the number of scores that actually changed."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            _learn_preferences(conn)
            snapshot = _Snapshot(conn, _load_weights(conn))
            count = _persist(conn, snapshot, snapshot.selected(status))
            conn.commit()
        return count

    def update_task_priority(self, task_id: UUID) -> Task:
        """Persist one intrinsic score and return the stored task."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            snapshot = _Snapshot(conn, _load_weights(conn))
            key = snapshot.require(task_id)
            _persist(conn, snapshot, [key])
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (key,)).fetchone()
            conn.commit()
        return Task.model_validate(dict(row))

    def get_top_priorities(self, limit: int = 10, match_skills: bool = False) -> list[Task]:
        """Rank actionable tasks by inherited score; optional skill readiness shares their read snapshot."""
        if limit < 0:
            raise ValueError("Priority limit must be nonnegative")
        if limit == 0:
            return []
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            snapshot = _Snapshot(conn, _load_weights(conn))
            keys = [key for key in snapshot.selected(None) if not snapshot.blockers[key]]
            if match_skills:
                from .planning import PlanningService, skill_levels  # noqa: PLC0415

                levels = skill_levels(conn)
                tasks = [
                    TaskWithDependencies.model_validate(
                        {**dict(snapshot.rows[key]), "tasks_blocked_count": len(snapshot.dependents[key])}
                    )
                    for key in keys
                ]
                ready = {
                    str(match.task_id)
                    for match in PlanningService(self.db_path).match_tasks(tasks, levels=levels)
                    if match.ready
                }
                keys = [key for key in keys if key in ready]
        effective = snapshot.effective()
        keys.sort(key=lambda key: (-effective[key], -snapshot.scores[key], snapshot.rows[key]["created_at"], key))
        return [
            Task.model_validate({**dict(snapshot.rows[key]), "priority_score": snapshot.scores[key]})
            for key in keys[:limit]
        ]

    def explain(self, task_id: UUID) -> dict:
        """Expose exact normalized weighted contributions in score points and inheritance separately."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            weights = _load_weights(conn)
            preference = conn.execute(
                "SELECT source, sample_count FROM priority_preferences WHERE singleton=1"
            ).fetchone()
            snapshot = _Snapshot(conn, weights)
        key = snapshot.require(task_id)
        return {
            "score": snapshot.scores[key],
            "effective_score": snapshot.effective()[key],
            "weights": weights.model_dump(),
            "preference_source": preference["source"] if preference else "default",
            "learning_samples": preference["sample_count"] if preference else 0,
            "learning_rate": LEARNING_RATE,
            "learning_method": (
                "90% issue defaults + 10% normalized(default weight * "
                "(0.5 + mean normalized factor in valid completed snapshots)); "
                "at least 20 snapshots; explicit custom weights are never changed"
            ),
            "components": {
                name: {
                    "raw": snapshot.raw[key][name],
                    "normalized": snapshot.normalized[key][name],
                    "weight": getattr(weights, name),
                    "contribution": 100 * snapshot.normalized[key][name] * getattr(weights, name),
                }
                for name in FACTOR_NAMES
            },
        }

    def adjust_weights(self, weights: PriorityWeights) -> None:
        """Persist explicit custom weights and atomically refresh active scores."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            _save_weights(conn, weights, "custom", 0)
            snapshot = _Snapshot(conn, weights)
            _persist(conn, snapshot, snapshot.selected(None))
            conn.commit()

    def history(self, task_id: UUID) -> list[dict]:
        """Read chronological changed-score events; a read never adds an event."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            if not conn.execute("SELECT 1 FROM tasks WHERE task_id = ?", (str(task_id),)).fetchone():
                raise TaskNotFoundError(task_id)
            rows = conn.execute(
                "SELECT event_id, score, recorded_at FROM priority_history WHERE task_id = ? ORDER BY event_id",
                (str(task_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def trend(self, task_id: UUID) -> str:
        """Compare the latest two changed scores, or report stable without enough evidence."""
        events = self.history(task_id)
        if len(events) < 2:  # noqa: PLR2004
            return "stable"
        difference = events[-1]["score"] - events[-2]["score"]
        return "rising" if difference > 0 else "falling" if difference < 0 else "stable"
