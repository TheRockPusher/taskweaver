"""Consumer-facing regressions for goals, learning, and skill readiness."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from taskweaver.database import planning as planning_module
from taskweaver.database.connection import get_connection
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.exceptions import TaskNotFoundError
from taskweaver.database.models import CompletionStatus, Task, TaskCreate, TaskUpdate
from taskweaver.database.planning import PlanningService
from taskweaver.database.repository import TaskRepository


@pytest.fixture
def planning(temp_db: Path) -> PlanningService:
    return PlanningService(temp_db)


def make_task(task_repo: TaskRepository, category: str = "general", **fields: object) -> Task:
    return task_repo.create_task(
        TaskCreate.model_validate(
            {
                "title": "Work",
                "duration_min": 60,
                "llm_value": 80,
                "requirement": "Deliver",
                "category": category,
                **fields,
            }
        )
    )


def test_empty_goal_and_link_lifecycle(planning: PlanningService, task_repo: TaskRepository) -> None:
    goal = planning.create_goal("Learn databases", "Ship a useful app")
    progress = planning.goal_progress(goal.goal_id)
    assert progress.total == 0
    assert progress.completed == 0
    assert progress.fraction == 0
    assert planning.list_goals() == [goal]
    assert planning.get_goal(goal.goal_id) == goal

    task = make_task(task_repo)
    assert planning.link_task(task.task_id, goal.goal_id).goal_id == goal.goal_id
    assert planning.goal_progress(goal.goal_id).total == 1
    assert planning.link_task(task.task_id, None).goal_id is None
    assert planning.goal_progress(goal.goal_id).total == 0

    updated = planning.update_goal(goal.goal_id, "Ship database app", "Release to users")
    assert updated.title == "Ship database app"
    assert updated.description == "Release to users"
    assert planning.update_goal(goal.goal_id).description is None
    planning.link_task(task.task_id, goal.goal_id)
    planning.delete_goal(goal.goal_id)
    assert planning.get_goal(goal.goal_id) is None
    preserved = task_repo.get_task(task.task_id)
    assert preserved is not None
    assert preserved.goal_id is None


def test_goal_progress_excludes_cancelled_denominator_and_numerator(
    planning: PlanningService, task_repo: TaskRepository
) -> None:
    goal = planning.create_goal("Deliver")
    completed = make_task(task_repo, goal_id=goal.goal_id)
    cancelled = make_task(task_repo, goal_id=goal.goal_id)
    make_task(task_repo, goal_id=goal.goal_id)
    planning.complete_task(completed.task_id, 60)
    planning.complete_task(cancelled.task_id, 20, status=CompletionStatus.CANCELLED)
    progress = planning.goal_progress(goal.goal_id)
    assert (progress.completed, progress.total, progress.cancelled, progress.fraction) == (1, 2, 1, 0.5)


def test_all_cancelled_goal_has_zero_progress(planning: PlanningService, task_repo: TaskRepository) -> None:
    goal = planning.create_goal("Abandoned")
    task = make_task(task_repo, goal_id=goal.goal_id)
    planning.complete_task(task.task_id, 10, status=CompletionStatus.CANCELLED)
    progress = planning.goal_progress(goal.goal_id)
    assert (progress.completed, progress.total, progress.cancelled, progress.fraction) == (0, 0, 1, 0)


def test_missing_goal_does_not_link_or_mutate(planning: PlanningService, task_repo: TaskRepository) -> None:
    missing = uuid4()
    assert planning.get_goal(missing) is None
    with pytest.raises(ValueError, match="Goal not found"):
        planning.goal_progress(missing)
    with pytest.raises(ValueError, match="Goal not found"):
        planning.update_goal(missing, "Missing")
    with pytest.raises(ValueError, match="Goal not found"):
        planning.delete_goal(missing)
    task = make_task(task_repo)
    with pytest.raises(ValueError, match="Goal not found"):
        planning.link_task(task.task_id, missing)
    unchanged = task_repo.get_task(task.task_id)
    assert unchanged is not None
    assert unchanged.goal_id is None


def test_skill_evidence_history_retains_progression_and_backfills(planning: PlanningService) -> None:
    observed = datetime(2026, 1, 1, tzinfo=UTC)
    beginner = planning.set_skill("database", 2, "Can identify table keys", observed)
    competent = planning.set_skill("database", 3, "Designed production schema", observed + timedelta(days=20))
    backfill = planning.set_skill("database", 1, "Needed rigid rules", observed - timedelta(days=10))
    assert planning.skill_history("database") == [backfill, beginner, competent]
    assert planning.list_skills() == [competent]
    reassessed = planning.set_skill("database", 2, "New domain reveals gaps", observed + timedelta(days=30))
    assert planning.list_skills() == [reassessed]
    assert len(planning.skill_history("database")) == 4
    assert beginner.evidence == "Can identify table keys"
    assert beginner.assessed_at == observed


@pytest.mark.parametrize("level", [0, 6])
def test_skill_levels_are_dreyfus_range(planning: PlanningService, level: int) -> None:
    with pytest.raises(ValueError, match="DreyfusLevel"):
        planning.set_skill("python", level, "Evidence")
    assert planning.list_skills() == []


def test_skill_assessment_requires_evidence_and_timestamp(planning: PlanningService) -> None:
    with pytest.raises(ValidationError):
        planning.set_skill("python", 2, "  ")
    with pytest.raises(ValidationError):
        planning.set_skill("  ", 2, "Evidence")
    with pytest.raises(ValueError, match="timezone"):
        planning.set_skill("python", 2, "Evidence", datetime(2026, 1, 1))
    assert planning.list_skills() == []


def test_skill_match_distinguishes_learning_gap_and_readiness(
    planning: PlanningService, task_repo: TaskRepository, dep_repo: TaskDependencyRepository
) -> None:
    planning.set_skill("python", 3, "Built maintained tools")
    ready = make_task(task_repo, skill_domain="python", required_skill_level=3)
    too_hard = make_task(task_repo, skill_domain="python", required_skill_level=4)
    unknown = make_task(task_repo, skill_domain="database", required_skill_level=1)
    unrestricted = make_task(task_repo)
    blocked = make_task(task_repo, skill_domain="python", required_skill_level=1)
    dep_repo.add_dependency(blocked.task_id, unrestricted.task_id)

    assert planning.match(ready.task_id).ready
    gap = planning.match(unknown.task_id)
    assert not gap.ready
    assert gap.learning_gap
    assert gap.known_level is None
    difficult = planning.match(too_hard.task_id)
    assert difficult.learning_gap
    assert difficult.known_level == 3
    blocker_match = planning.match(blocked.task_id)
    assert not blocker_match.ready
    assert blocker_match.blocked
    recommendations = planning.recommendations()
    assert {task.task_id for task in recommendations.ready} == {ready.task_id, unrestricted.task_id}
    assert {match.task_id for match in recommendations.learning_gaps} == {too_hard.task_id, unknown.task_id}
    planning.complete_task(unrestricted.task_id, 60)
    assert planning.match(blocked.task_id).ready
    assert not planning.match(unrestricted.task_id).ready


def test_blocked_learning_gaps_are_not_recommended(
    planning: PlanningService, task_repo: TaskRepository, dep_repo: TaskDependencyRepository
) -> None:
    blocker = make_task(task_repo)
    task = make_task(task_repo, skill_domain="unknown", required_skill_level=2)
    dep_repo.add_dependency(task.task_id, blocker.task_id)
    match = planning.match(task.task_id)
    assert match.blocked
    assert match.learning_gap
    assert not match.ready
    assert planning.recommendations().learning_gaps == []


def test_batch_skill_matching_accepts_captured_levels(planning: PlanningService, task_repo: TaskRepository) -> None:
    planning.set_skill("python", 3, "Built maintained tools")
    make_task(task_repo, skill_domain="python", required_skill_level=3)
    tasks = task_repo.list_tasks_with_deps()
    assert planning.match_tasks(tasks)[0].ready
    captured = planning.match_tasks(tasks, levels={"python": 2})[0]
    assert (captured.known_level, captured.required_level, captured.ready) == (2, 3, False)
    unknown = planning.match_tasks(tasks, levels={})[0]
    assert unknown.known_level is None
    assert unknown.learning_gap
    assert not unknown.ready


@pytest.mark.parametrize("operation", ["match", "recommendations"])
def test_skill_readiness_cannot_combine_old_requirement_and_new_level(
    planning: PlanningService, task_repo: TaskRepository, temp_db: Path, monkeypatch, operation
) -> None:
    observed = datetime(2026, 1, 1, tzinfo=UTC)
    with get_connection(temp_db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
    planning.set_skill("python", 2, "Beginning practice", observed)
    task = make_task(task_repo, skill_domain="python", required_skill_level=3)
    assert not planning.match(task.task_id).ready
    wrote = False

    def raise_requirement_then_skill(query):
        nonlocal wrote
        if not wrote and "FROM skill_assessments" in query:
            with get_connection(temp_db) as writer:
                writer.execute("UPDATE tasks SET required_skill_level=5 WHERE task_id=?", (str(task.task_id),))
                writer.commit()
                writer.execute(
                    "INSERT INTO skill_assessments(assessment_id,domain,level,evidence,assessed_at,recorded_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        str(uuid4()),
                        "python",
                        3,
                        "More practice",
                        (observed + timedelta(days=1)).isoformat(),
                        (observed + timedelta(days=1)).isoformat(),
                    ),
                )
                writer.commit()
            wrote = True

    @contextmanager
    def concurrent_connection(db_path):
        with get_connection(db_path) as conn:
            conn.set_trace_callback(raise_requirement_then_skill)
            yield conn

    monkeypatch.setattr(planning_module, "get_connection", concurrent_connection)
    if operation == "match":
        captured = planning.match(task.task_id)
    else:
        result = planning.recommendations()
        assert result.ready == []
        assert len(result.learning_gaps) == 1
        captured = result.learning_gaps[0]
    assert wrote
    assert (captured.required_level, captured.known_level, captured.ready) == (3, 2, False)
    latest = planning.match(task.task_id)
    assert (latest.required_level, latest.known_level, latest.ready) == (5, 3, False)
    assert planning.recommendations().ready == []


def test_estimate_requires_three_completed_category_samples(
    planning: PlanningService, task_repo: TaskRepository
) -> None:
    empty = planning.estimate("database", 60)
    assert (empty.adjusted_minutes, empty.multiplier, empty.sample_count) == (60, 1, 0)
    assert empty.confidence.median_ratio is None
    assert empty.confidence.median_absolute_deviation is None
    for actual in (60, 180):
        task = make_task(task_repo, "database")
        planning.complete_task(task.task_id, actual)
    partial = planning.estimate("database", 60)
    assert partial.adjusted_minutes == 60
    assert partial.sample_count == 2
    assert not partial.confidence.automatic_adjustment
    assert partial.confidence.median_ratio == 2
    assert partial.confidence.median_absolute_deviation == 1
    task = make_task(task_repo, "database")
    planning.complete_task(task.task_id, 120)
    learned = planning.estimate("database", 60)
    assert (learned.adjusted_minutes, learned.multiplier, learned.sample_count) == (120, 2, 3)
    assert learned.confidence.automatic_adjustment
    assert learned.confidence.median_absolute_deviation == 1
    isolated = planning.estimate("frontend", 60)
    assert (isolated.adjusted_minutes, isolated.sample_count) == (60, 0)


def test_cancelled_samples_never_adjust_estimates(planning: PlanningService, task_repo: TaskRepository) -> None:
    for _ in range(3):
        task = make_task(task_repo, "database")
        planning.complete_task(task.task_id, 600, status=CompletionStatus.CANCELLED)
    task = make_task(task_repo, "database")
    planning.complete_task(task.task_id, 120)
    estimate = planning.estimate("database", 60)
    assert (estimate.multiplier, estimate.sample_count, estimate.adjusted_minutes) == (1, 1, 60)
    insight = planning.insights()[0]
    assert (insight.category, insight.completed, insight.cancelled) == ("database", 1, 3)
    assert insight.estimate.sample_count == 1


def test_automatic_creation_adjusts_once_and_snapshots_remain_immutable(
    planning: PlanningService, task_repo: TaskRepository
) -> None:
    for _ in range(3):
        task = make_task(task_repo, "database")
        planning.complete_task(task.task_id, 120)
    learned_task = make_task(task_repo, "database")
    assert learned_task.duration_min == 120
    assert learned_task.raw_duration_min == 60
    completion = planning.complete_task(learned_task.task_id, 120)
    assert (completion.duration_expected, completion.raw_duration_min, completion.category) == (120, 60, "database")
    assert planning.estimate("database", 60).multiplier == 2
    next_task = make_task(task_repo, "database")
    assert (next_task.duration_min, next_task.raw_duration_min) == (120, 60)
    task_repo.update_task(learned_task.task_id, TaskUpdate(duration_min=300, category="frontend"))
    repeated = planning.complete_task(learned_task.task_id, 120)
    assert repeated == completion
    assert planning.estimate("database", 60).multiplier == 2
    assert planning.estimate("frontend", 60).sample_count == 0
    assert planning.insights()[0].category == "database"


def test_speed_never_changes_assessed_skill(planning: PlanningService, task_repo: TaskRepository) -> None:
    assessed = planning.set_skill("python", 1, "Needs explicit step-by-step guidance")
    for _ in range(3):
        task = make_task(task_repo, "python", skill_domain="python", required_skill_level=1)
        planning.complete_task(task.task_id, 5)
    assert planning.list_skills() == [assessed]
    assert planning.skill_history("python") == [assessed]
    too_hard = make_task(task_repo, skill_domain="python", required_skill_level=2)
    assert not planning.match(too_hard.task_id).ready


def test_estimate_rounds_up_without_mutating_baseline(planning: PlanningService, task_repo: TaskRepository) -> None:
    for _ in range(3):
        task = make_task(task_repo, "fractional", duration_min=60)
        planning.complete_task(task.task_id, 80)
    estimate = planning.estimate("fractional", 10)
    assert estimate.adjusted_minutes == 14
    assert estimate.baseline_minutes == 10
    assert estimate.confidence.median_absolute_deviation == 0
    with pytest.raises(ValueError, match="positive"):
        planning.estimate("fractional", 0)


def test_different_category_patterns_never_pool(planning: PlanningService, task_repo: TaskRepository) -> None:
    for _ in range(3):
        database = make_task(task_repo, "database")
        frontend = make_task(task_repo, "frontend")
        planning.complete_task(database.task_id, 120)
        planning.complete_task(frontend.task_id, 30)
    database_estimate = planning.estimate("database", 60)
    frontend_estimate = planning.estimate("frontend", 60)
    assert (database_estimate.multiplier, database_estimate.sample_count) == (2, 3)
    assert (frontend_estimate.multiplier, frontend_estimate.sample_count) == (0.5, 3)
    insights = {insight.category: insight for insight in planning.insights()}
    assert set(insights) == {"database", "frontend"}
    assert insights["database"].estimate.confidence.median_ratio == 2
    assert insights["frontend"].estimate.confidence.median_ratio == 0.5


def test_match_missing_task_reports_missing_work(planning: PlanningService) -> None:
    with pytest.raises(TaskNotFoundError):
        planning.match(uuid4())


def test_ready_work_inherits_urgent_downstream_score_until_goal_closes(
    planning: PlanningService, task_repo: TaskRepository, dep_repo: TaskDependencyRepository
) -> None:
    independent = make_task(task_repo, title="Independent", urgency=4, importance=4, effort=2)
    blocker = make_task(task_repo, title="Blocker", urgency=1, importance=1, effort=5)
    downstream = make_task(task_repo, title="Urgent goal", urgency=5, importance=5, effort=1)
    dep_repo.add_dependency(downstream.task_id, blocker.task_id)
    assert [task.task_id for task in planning.recommendations().ready] == [
        blocker.task_id,
        independent.task_id,
    ]
    task_repo.update_task(blocker.task_id, TaskUpdate(skill_domain="python", required_skill_level=3))
    assert [task.task_id for task in planning.recommendations().ready] == [independent.task_id]
    planning.set_skill("python", 3, "Independent implementations")
    assert [task.task_id for task in planning.recommendations().ready] == [
        blocker.task_id,
        independent.task_id,
    ]
    planning.complete_task(downstream.task_id, 60)
    assert [task.task_id for task in planning.recommendations().ready] == [
        independent.task_id,
        blocker.task_id,
    ]
