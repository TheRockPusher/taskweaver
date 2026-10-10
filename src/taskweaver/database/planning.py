"""Goals, assessed skills, and transparent duration learning."""

import sqlite3
from datetime import UTC, datetime
from enum import IntEnum
from fractions import Fraction
from heapq import heapify, heappop, heappush
from math import ceil
from pathlib import Path
from statistics import median
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .completion_repository import CompletionRepository
from .connection import get_connection, get_database_path
from .exceptions import DependencyError, TaskNotFoundError
from .models import SQLITE_MAX_INTEGER, Completion, CompletionStatus, Task, TaskUpdate, TaskWithDependencies
from .priority_service import _load_weights, _Snapshot

MINIMUM_DURATION_SAMPLES = 3


class DreyfusLevel(IntEnum):
    """Explicit assessments, never inferred from task speed."""

    NOVICE = 1
    ADVANCED_BEGINNER = 2
    COMPETENT = 3
    PROFICIENT = 4
    EXPERT = 5


class Goal(BaseModel):
    """A named outcome linked to tasks."""

    goal_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GoalProgress(BaseModel):
    """Completed / all noncancelled linked tasks; empty goals have zero progress."""

    goal: Goal
    completed: int
    total: int
    cancelled: int
    fraction: float


class SkillAssessment(BaseModel):
    """An immutable assessment with supporting evidence and its observation time."""

    assessment_id: UUID = Field(default_factory=uuid4)
    domain: str = Field(min_length=1)
    level: DreyfusLevel
    evidence: str = Field(min_length=1)
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SkillMatch(BaseModel):
    """Readiness considers both evidence-backed skill and active blockers."""

    task_id: UUID
    ready: bool
    blocked: bool
    known_level: int | None
    required_level: int | None
    learning_gap: bool
    reason: str


class Recommendations(BaseModel):
    """Eligible work and separate learning gaps, never blocked work."""

    ready: list[Task]
    learning_gaps: list[SkillMatch]


class WorkAnalysis(BaseModel):
    """Working-time DAG analysis, assuming unlimited parallel capacity.

    Durations exclude skill-learning time and do not predict completion dates.
    Quick wins use CD3 value/minute, not inherited MCDA scores.
    """

    critical_path: list[Task]
    critical_path_minutes: int
    quick_wins: list[Task]


class EstimateConfidence(BaseModel):
    """Observed sample count and ratio dispersion, not a probability of success."""

    sample_count: int
    median_ratio: float | None
    median_absolute_deviation: float | None
    automatic_adjustment: bool


class DurationEstimate(BaseModel):
    """A category multiplier applied once to the caller's raw baseline, within SQLite's integer range."""

    category: str
    baseline_minutes: int = Field(ge=1, le=SQLITE_MAX_INTEGER)
    adjusted_minutes: int = Field(ge=1, le=SQLITE_MAX_INTEGER)
    multiplier: float
    sample_count: int
    confidence: EstimateConfidence


class CategoryInsight(BaseModel):
    """Historical completed and cancelled counts with raw-baseline duration evidence."""

    category: str
    completed: int
    cancelled: int
    estimate: DurationEstimate


def estimate_duration(conn: sqlite3.Connection, category: str, baseline_minutes: int) -> DurationEstimate:
    """Estimate from completed actual/raw ratios; require three valid samples.

    Args:
        conn: Existing database connection, without opening or committing a transaction.
        category: Exact category to learn independently from other categories.
        baseline_minutes: Raw unadjusted estimate; never supply an adjusted estimate.

    Returns:
        Rounded-up adjusted minutes and descriptive count/median/dispersion evidence.
        Ratios remain exact until rounding so whole-minute results are not inflated
        by floating-point error, and unadjusted large baselines retain every minute.
    """
    if baseline_minutes < 1:
        raise ValueError("Baseline duration must be positive")
    rows = conn.execute(
        "SELECT duration_actual, raw_duration_min FROM completion "
        "WHERE category = ? AND status = 'completed' "
        "AND duration_actual > 0 AND raw_duration_min > 0",
        (category,),
    ).fetchall()
    ratios = [Fraction(row[0], row[1]) for row in rows]
    center = median(ratios) if ratios else None
    dispersion = float(median(abs(ratio - center) for ratio in ratios)) if center is not None else None
    automatic = len(ratios) >= MINIMUM_DURATION_SAMPLES
    multiplier = center if automatic and center is not None else Fraction(1)
    return DurationEstimate(
        category=category,
        baseline_minutes=baseline_minutes,
        adjusted_minutes=max(1, ceil(baseline_minutes * multiplier)),
        multiplier=float(multiplier),
        sample_count=len(ratios),
        confidence=EstimateConfidence(
            sample_count=len(ratios),
            median_ratio=float(center) if center is not None else None,
            median_absolute_deviation=dispersion,
            automatic_adjustment=automatic,
        ),
    )


def _latest_skill_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM (SELECT *, ROW_NUMBER() OVER ("
        "PARTITION BY domain ORDER BY assessed_at DESC, recorded_at DESC, assessment_id DESC"
        ") AS position FROM skill_assessments) WHERE position = 1 ORDER BY domain"
    ).fetchall()


def skill_levels(conn: sqlite3.Connection) -> dict[str, int]:
    """Read latest observed levels in the caller's snapshot, without opening or committing a transaction."""
    return {row["domain"]: int(row["level"]) for row in _latest_skill_rows(conn)}


class PlanningService:
    """Persistent goals and assessed skills, plus completion-based duration learning."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path if db_path is not None else get_database_path()

    def create_goal(self, title: str, description: str | None = None) -> Goal:
        """Create a goal without implicitly creating or attaching tasks."""
        goal = Goal(title=title.strip(), description=description)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO goals (goal_id, title, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (
                    str(goal.goal_id),
                    goal.title,
                    goal.description,
                    goal.created_at.isoformat(),
                    goal.updated_at.isoformat(),
                ),
            )
            conn.commit()
        return goal

    def list_goals(self) -> list[Goal]:
        """List goals in creation order."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM goals ORDER BY created_at, goal_id").fetchall()
        return [Goal.model_validate(dict(row)) for row in rows]

    def get_goal(self, goal_id: UUID) -> Goal | None:
        """Return a goal, or None when it does not exist."""
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM goals WHERE goal_id = ?", (str(goal_id),)).fetchone()
        return Goal.model_validate(dict(row)) if row is not None else None

    def goal_progress(self, goal_id: UUID) -> GoalProgress:
        """Count completed tasks over all noncancelled tasks; report cancellations separately."""
        goal = self.get_goal(goal_id)
        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM tasks WHERE goal_id = ? GROUP BY status", (str(goal_id),)
            ).fetchall()
        counts = {row["status"]: row["count"] for row in rows}
        cancelled = counts.get("cancelled", 0)
        completed = counts.get("completed", 0)
        total = sum(counts.values()) - cancelled
        return GoalProgress(
            goal=goal,
            completed=completed,
            total=total,
            cancelled=cancelled,
            fraction=completed / total if total else 0.0,
        )

    def update_goal(self, goal_id: UUID, title: str | None = None, description: str | None = None) -> Goal:
        """Update a title and replace the description; None clears the description."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM goals WHERE goal_id = ?", (str(goal_id),)).fetchone()
            if row is None:
                raise ValueError(f"Goal not found: {goal_id}")
            data = dict(row)
            data.update(description=description, updated_at=datetime.now(UTC))
            if title is not None:
                data["title"] = title.strip()
            goal = Goal.model_validate(data)
            conn.execute(
                "UPDATE goals SET title = ?, description = ?, updated_at = ? WHERE goal_id = ?",
                (goal.title, goal.description, goal.updated_at.isoformat(), str(goal_id)),
            )
            conn.commit()
        return goal

    def delete_goal(self, goal_id: UUID) -> None:
        """Delete a goal and unlink its tasks, without deleting work or history."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute("DELETE FROM goals WHERE goal_id = ?", (str(goal_id),))
            if not cursor.rowcount:
                raise ValueError(f"Goal not found: {goal_id}")
            conn.commit()

    def link_task(self, task_id: UUID, goal_id: UUID | None) -> Task:
        """Link or explicitly unlink a task through the shared task update contract."""
        # Repository imports estimate_duration from this module; defer to break the cycle.
        from .repository import TaskRepository  # noqa: PLC0415

        return TaskRepository(self.db_path).update_task(task_id, TaskUpdate(goal_id=goal_id))

    def set_skill(self, domain: str, level: int, evidence: str, assessed_at: datetime | None = None) -> SkillAssessment:
        """Append an evidence-backed Dreyfus assessment, retaining every prior assessment."""
        observed = assessed_at if assessed_at is not None else datetime.now(UTC)
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("Assessment timestamp must include a timezone")
        assessment = SkillAssessment(
            domain=domain.strip(),
            level=DreyfusLevel(level),
            evidence=evidence.strip(),
            assessed_at=observed.astimezone(UTC),
        )
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO skill_assessments (assessment_id, domain, level, evidence, assessed_at, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(assessment.assessment_id),
                    assessment.domain,
                    int(assessment.level),
                    assessment.evidence,
                    assessment.assessed_at.isoformat(),
                    assessment.recorded_at.isoformat(),
                ),
            )
            conn.commit()
        return assessment

    def list_skills(self) -> list[SkillAssessment]:
        """Return the latest observed assessment per domain; historical backfills do not upgrade it."""
        with get_connection(self.db_path) as conn:
            rows = _latest_skill_rows(conn)
        return [SkillAssessment.model_validate(dict(row)) for row in rows]

    def skill_history(self, domain: str) -> list[SkillAssessment]:
        """Return chronological assessments, including corrections and regressions."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM skill_assessments WHERE domain = ? ORDER BY assessed_at, recorded_at, assessment_id",
                (domain.strip(),),
            ).fetchall()
        return [SkillAssessment.model_validate(dict(row)) for row in rows]

    def match_tasks(
        self, tasks: list[TaskWithDependencies], *, levels: dict[str, int] | None = None
    ) -> list[SkillMatch]:
        """Match with captured levels, or load latest levels when the caller has no shared snapshot."""
        if levels is None:
            with get_connection(self.db_path) as conn:
                levels = skill_levels(conn)
        return [self._match(task, levels) for task in tasks]

    @staticmethod
    def _match(task: TaskWithDependencies, levels: dict[str, int]) -> SkillMatch:
        required = task.required_skill_level
        known = levels.get(task.skill_domain) if task.skill_domain is not None else None
        needs_skill = task.skill_domain is not None or required is not None
        gap = needs_skill and (known is None or known < (required or int(DreyfusLevel.NOVICE)))
        active = task.status in ("pending", "in_progress")
        if not active:
            reason = "Task is closed"
        elif task.is_blocked:
            reason = "Task has active blockers"
        elif gap:
            reason = "Skill assessment missing" if known is None else "Required skill exceeds assessed level"
        else:
            reason = "No unmet skill requirements or active blockers"
        return SkillMatch(
            task_id=task.task_id,
            ready=active and not task.is_blocked and not gap,
            blocked=task.is_blocked,
            known_level=known,
            required_level=required,
            learning_gap=gap,
            reason=reason,
        )

    def match(self, task_id: UUID) -> SkillMatch:
        """Read one task, its active dependencies, and latest skill levels in a single snapshot."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            row = conn.execute(
                "SELECT t.*, (SELECT COUNT(*) FROM task_dependencies d JOIN tasks b ON b.task_id = d.blocker_id "
                "WHERE d.task_id = t.task_id AND b.status IN ('pending', 'in_progress')) AS active_blocker_count "
                "FROM tasks t WHERE t.task_id = ?",
                (str(task_id),),
            ).fetchone()
            if row is None:
                raise TaskNotFoundError(task_id)
            levels = skill_levels(conn)
        return self.match_tasks([TaskWithDependencies.model_validate(dict(row))], levels=levels)[0]

    def recommendations(self) -> Recommendations:
        """Rank ready work by inherited MCDA; capture dependencies and skills in one snapshot."""
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            snapshot = _Snapshot(conn, _load_weights(conn))
            levels = skill_levels(conn)
        effective = snapshot.effective()
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
        tasks.sort(
            key=lambda task: (
                -effective[str(task.task_id)],
                -(task.priority_score or 0.0),
                task.created_at,
                str(task.task_id),
            )
        )
        matches = self.match_tasks(tasks, levels=levels)
        return Recommendations(
            ready=[task for task, match in zip(tasks, matches, strict=True) if match.ready],
            learning_gaps=[match for match in matches if match.learning_gap and not match.blocked],
        )

    def work_analysis(self, max_minutes: int = 30, limit: int = 5) -> WorkAnalysis:
        """Find the longest active duration path and ready CD3-ranked quick wins.

        Ties use creation time then ID, including equal-duration predecessors.
        Closed work and its edges are excluded; active cycles are errors.
        """
        if max_minutes <= 0:
            raise ValueError("Quick-win maximum minutes must be positive")
        if limit < 0:
            raise ValueError("Quick-win limit must be nonnegative")
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            snapshot = _Snapshot(conn, _load_weights(conn))
            levels = skill_levels(conn)
        tasks = {
            key: TaskWithDependencies.model_validate(
                {
                    **dict(snapshot.rows[key]),
                    "priority_score": snapshot.scores[key],
                    "tasks_blocked_count": len(snapshot.dependents[key]),
                    "active_blocker_count": len(snapshot.blockers[key]),
                }
            )
            for key in snapshot.selected(None)
        }
        stable = {key: (task.created_at, key) for key, task in tasks.items()}
        remaining = {key: len(snapshot.blockers[key]) for key in tasks}
        queue = [stable[key] for key, count in remaining.items() if not count]
        heapify(queue)
        totals = {key: task.duration_min for key, task in tasks.items()}
        predecessor: dict[str, str] = {}
        processed = 0
        while queue:
            _, key = heappop(queue)
            processed += 1
            for child in snapshot.dependents[key]:
                candidate = totals[key] + tasks[child].duration_min
                previous = predecessor.get(child)
                if candidate > totals[child] or (
                    candidate == totals[child] and (previous is None or stable[key] < stable[previous])
                ):
                    totals[child] = candidate
                    predecessor[child] = key
                remaining[child] -= 1
                if not remaining[child]:
                    heappush(queue, stable[child])
        if processed != len(tasks):
            raise DependencyError("Cannot analyze a cyclic task dependency graph")
        path: list[Task] = []
        endpoint = min(tasks, key=lambda key: (-totals[key], stable[key])) if tasks else None
        minutes = totals[endpoint] if endpoint is not None else 0
        while endpoint is not None:
            path.append(tasks[endpoint])
            endpoint = predecessor.get(endpoint)
        path.reverse()
        quick_wins = [
            task for task in tasks.values() if task.duration_min <= max_minutes and self._match(task, levels).ready
        ]
        quick_wins.sort(key=lambda task: (-task.priority, task.created_at, str(task.task_id)))
        return WorkAnalysis(
            critical_path=path,
            critical_path_minutes=minutes,
            quick_wins=quick_wins[:limit],
        )

    def estimate(self, category: str, baseline_minutes: int) -> DurationEstimate:
        """Apply learned category ratios once to an immutable raw baseline."""
        with get_connection(self.db_path) as conn:
            return estimate_duration(conn, category, baseline_minutes)

    def insights(self) -> list[CategoryInsight]:
        """Describe historical completion categories, unaffected by later task edits."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT category, SUM(status = 'completed') AS completed, SUM(status = 'cancelled') AS cancelled "
                "FROM completion GROUP BY category ORDER BY category"
            ).fetchall()
            return [
                CategoryInsight(
                    category=row["category"],
                    completed=row["completed"],
                    cancelled=row["cancelled"],
                    estimate=estimate_duration(conn, row["category"], 1),
                )
                for row in rows
            ]

    def complete_task(
        self,
        task_id: UUID,
        actual_minutes: int,
        conclusion: str | None = None,
        status: CompletionStatus = CompletionStatus.COMPLETED,
    ) -> Completion:
        """Close work and record one snapshot atomically; exact retries are harmless."""
        return CompletionRepository(self.db_path).complete_task(task_id, actual_minutes, conclusion, status)
