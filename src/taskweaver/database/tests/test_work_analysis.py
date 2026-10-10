"""Real SQLite duration-path and ready CD3 analysis regressions."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from taskweaver.database.connection import get_connection
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.exceptions import DependencyError
from taskweaver.database.models import Task, TaskCreate, TaskStatus, TaskUpdate
from taskweaver.database.planning import PlanningService
from taskweaver.database.repository import TaskRepository


def make_task(repo: TaskRepository, title: str, minutes: int, **fields: object) -> Task:
    return repo.create_task(
        TaskCreate.model_validate(
            {
                "title": title,
                "duration_min": minutes,
                "llm_value": 50,
                "requirement": "Deliver",
                **fields,
            }
        )
    )


def test_fork_join_duration_not_mcda(
    temp_db: Path, task_repo: TaskRepository, dep_repo: TaskDependencyRepository
) -> None:
    root = make_task(task_repo, "Root", 10)
    long = make_task(task_repo, "Long low MCDA", 90, urgency=1, importance=1, effort=5)
    short = make_task(task_repo, "Short high MCDA", 20, urgency=5, importance=5, effort=1)
    join = make_task(task_repo, "Join", 10)
    dep_repo.add_dependency(long.task_id, root.task_id)
    dep_repo.add_dependency(short.task_id, root.task_id)
    dep_repo.add_dependency(join.task_id, long.task_id)
    dep_repo.add_dependency(join.task_id, short.task_id)
    result = PlanningService(temp_db).work_analysis()
    assert [task.task_id for task in result.critical_path] == [root.task_id, long.task_id, join.task_id]
    assert result.critical_path_minutes == 110
    assert short.priority_score is not None
    assert long.priority_score is not None
    assert short.priority_score > long.priority_score
    assert [task.task_id for task in result.quick_wins] == [root.task_id]


def test_closed_nodes_edges_ignored(temp_db: Path, task_repo: TaskRepository) -> None:
    completed = make_task(task_repo, "Completed", 1000)
    cancelled = make_task(task_repo, "Cancelled", 2000)
    ready = make_task(task_repo, "Ready", 20)
    task_repo.update_task(completed.task_id, TaskUpdate(status=TaskStatus.COMPLETED))
    task_repo.update_task(cancelled.task_id, TaskUpdate(status=TaskStatus.CANCELLED))
    # Simulate stale legacy edges, including a closed-node cycle.
    with get_connection(temp_db) as conn:
        conn.executemany(
            "INSERT INTO task_dependencies (dependency_id, created_at, task_id, blocker_id) "
            "VALUES (lower(hex(randomblob(16))), CURRENT_TIMESTAMP, ?, ?)",
            [
                (str(ready.task_id), str(completed.task_id)),
                (str(completed.task_id), str(cancelled.task_id)),
                (str(cancelled.task_id), str(completed.task_id)),
            ],
        )
        conn.commit()
    result = PlanningService(temp_db).work_analysis()
    assert result.critical_path_minutes == 20
    assert [task.task_id for task in result.critical_path] == [ready.task_id]
    assert [task.task_id for task in result.quick_wins] == [ready.task_id]


def test_quick_wins_use_cd3_readiness_cutoff_and_limit(
    temp_db: Path, task_repo: TaskRepository, dep_repo: TaskDependencyRepository
) -> None:
    service = PlanningService(temp_db)
    low = make_task(task_repo, "High MCDA low CD3", 20, llm_value=10, urgency=5, importance=5)
    high = make_task(task_repo, "Low MCDA high CD3", 10, llm_value=90, urgency=1, importance=1)
    missing = make_task(task_repo, "Unknown skill", 5, skill_domain="unknown", required_skill_level=1)
    insufficient = make_task(task_repo, "Skill gap", 5, skill_domain="python", required_skill_level=4)
    skilled = make_task(task_repo, "Skilled", 30, skill_domain="python", required_skill_level=2)
    blocked = make_task(task_repo, "Blocked", 1)
    make_task(task_repo, "Too long", 31)
    service.set_skill("python", 2, "Observed work")
    dep_repo.add_dependency(blocked.task_id, high.task_id)
    result = service.work_analysis()
    assert [task.task_id for task in result.quick_wins] == [high.task_id, skilled.task_id, low.task_id]
    assert {missing.task_id, insufficient.task_id, blocked.task_id}.isdisjoint(
        task.task_id for task in result.quick_wins
    )
    assert [task.task_id for task in service.work_analysis(limit=1).quick_wins] == [high.task_id]
    assert service.work_analysis(limit=0).quick_wins == []
    assert [task.task_id for task in service.work_analysis(max_minutes=10).quick_wins] == [high.task_id]


def test_equal_duration_and_cd3_ties_are_stable(
    temp_db: Path, task_repo: TaskRepository, dep_repo: TaskDependencyRepository
) -> None:
    first = make_task(task_repo, "First", 10)
    second = make_task(task_repo, "Second", 10)
    join = make_task(task_repo, "Join", 10)
    # Equal creation timestamps exercise UUID fallback independent of SQL edge order.
    with get_connection(temp_db) as conn:
        conn.execute("UPDATE tasks SET created_at = ?", (datetime(2026, 1, 1, tzinfo=UTC).isoformat(),))
        conn.commit()
    dep_repo.add_dependency(join.task_id, second.task_id)
    dep_repo.add_dependency(join.task_id, first.task_id)
    ordered = sorted([first.task_id, second.task_id], key=str)
    result = PlanningService(temp_db).work_analysis()
    assert [task.task_id for task in result.critical_path] == [ordered[0], join.task_id]
    assert [task.task_id for task in result.quick_wins] == ordered


def test_empty_analysis(temp_db: Path) -> None:
    result = PlanningService(temp_db).work_analysis()
    assert result.critical_path == []
    assert result.critical_path_minutes == 0
    assert result.quick_wins == []


@pytest.mark.parametrize(("max_minutes", "limit"), [(0, 5), (-1, 5), (30, -1)])
def test_invalid_bounds(temp_db: Path, max_minutes: int, limit: int) -> None:
    with pytest.raises(ValueError, match=r"minutes|limit"):
        PlanningService(temp_db).work_analysis(max_minutes, limit)


def test_corrupt_active_cycle_raises(temp_db: Path, task_repo: TaskRepository) -> None:
    first = make_task(task_repo, "First", 10)
    second = make_task(task_repo, "Second", 20)
    with get_connection(temp_db) as conn:
        conn.executemany(
            "INSERT INTO task_dependencies (dependency_id, created_at, task_id, blocker_id) "
            "VALUES (lower(hex(randomblob(16))), CURRENT_TIMESTAMP, ?, ?)",
            [
                (str(first.task_id), str(second.task_id)),
                (str(second.task_id), str(first.task_id)),
            ],
        )
        conn.commit()
    with pytest.raises(DependencyError, match="cyclic"):
        PlanningService(temp_db).work_analysis(limit=0)
