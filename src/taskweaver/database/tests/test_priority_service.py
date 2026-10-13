"""Behavioral regression tests for normalized MCDA and actionable priority ranking."""

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from uuid import uuid4

import pytest
from pydantic import ValidationError

from taskweaver.database import planning, priority_service
from taskweaver.database.connection import get_connection
from taskweaver.database.exceptions import DependencyError, TaskNotFoundError
from taskweaver.database.models import CompletionCreate, CompletionStatus, TaskCreate, TaskStatus, TaskUpdate
from taskweaver.database.priority_service import (
    FACTOR_NAMES,
    PriorityService,
    PriorityWeights,
    completion_priority_factors,
    refresh_priorities,
)

NOW = datetime(2026, 10, 10, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(priority_service, "_now", lambda: NOW)


def _insert_tasks(  # noqa: PLR0913
    conn,
    count=1,
    *,
    urgency=3,
    importance=3,
    effort=3,
    created_at=NOW,
    status="pending",
):
    ids = [uuid4() for _ in range(count)]
    conn.executemany(
        "INSERT INTO tasks(task_id,title,status,created_at,updated_at,duration_min,raw_duration_min,"
        "llm_value,requirement,urgency,importance,effort) VALUES(?,?,?,?,?,30,30,50,'Delivered',?,?,?)",
        [
            (str(key), f"Task {index}", status, created_at.isoformat(), NOW.isoformat(), urgency, importance, effort)
            for index, key in enumerate(ids)
        ],
    )
    return ids


def _edge(conn, task_id, blocker_id):
    conn.execute(
        "INSERT INTO task_dependencies(dependency_id,task_id,blocker_id,created_at) VALUES(?,?,?,?)",
        (str(uuid4()), str(task_id), str(blocker_id), NOW.isoformat()),
    )


def _completion(conn, task_id, factors, *, status="completed"):
    conn.execute(
        "INSERT INTO completion(completion_id,task_id,status,closed_at,duration_expected,duration_actual,"
        "created_at,raw_duration_min,category,priority_factors) VALUES(?,?,?,?,30,30,?,30,'general',?)",
        (str(uuid4()), str(task_id), status, NOW.isoformat(), NOW.isoformat(), factors),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"urgency": -0.1},
        {"age": float("nan")},
        {"dependencies": float("inf")},
        {"effort": 0.2},
        {"urgency": 0, "importance": 0, "effort": 0, "dependencies": 0, "age": 0},
    ],
)
def test_weights_reject_invalid_scales(changes):
    with pytest.raises(ValidationError):
        PriorityWeights(**changes)


def test_default_midpoint_and_exact_explanation(temp_db):
    with get_connection(temp_db) as conn:
        task_id = _insert_tasks(conn)[0]
        conn.commit()
    service = PriorityService(temp_db)
    explanation = service.explain(task_id)
    assert service.weights == PriorityWeights(urgency=0.30, importance=0.35, effort=0.15, dependencies=0.10, age=0.10)
    assert explanation["score"] == 40.0
    assert sum(part["contribution"] for part in explanation["components"].values()) == pytest.approx(40)
    assert explanation["components"]["effort"] == {
        "raw": 3.0,
        "normalized": 0.5,
        "weight": 0.15,
        "contribution": 7.5,
    }
    assert service.history(task_id) == []
    assert service.trend(task_id) == "stable"


def test_bounds_age_and_dependency_caps(temp_db):
    with get_connection(temp_db) as conn:
        lowest = _insert_tasks(conn, urgency=1, importance=1, effort=5, created_at=NOW + timedelta(days=5))[0]
        highest = _insert_tasks(conn, urgency=5, importance=5, effort=1, created_at=NOW - timedelta(days=90))[0]
        for dependent in _insert_tasks(conn, 12):
            _edge(conn, dependent, highest)
        conn.commit()
    service = PriorityService(temp_db)
    assert service.calculate_priority(lowest) == 0
    assert service.calculate_priority(highest) == 100
    explanation = service.explain(highest)
    assert explanation["components"]["dependencies"]["raw"] == 12
    assert explanation["components"]["dependencies"]["normalized"] == 1
    assert explanation["components"]["age"]["normalized"] == 1
    assert service.explain(lowest)["components"]["age"]["normalized"] == 0


def test_age_partial_naive_timestamps_and_rounding(temp_db):
    with get_connection(temp_db) as conn:
        task_id = _insert_tasks(conn, created_at=(NOW - timedelta(days=1.5)).replace(tzinfo=None))[0]
        conn.commit()
    assert PriorityService(temp_db).calculate_priority(task_id) == 40.5


def test_active_dependency_transitions_refresh_scores(temp_db, task_repo, dep_repo):
    blocker = task_repo.create_task(TaskCreate(title="Blocker", duration_min=30, llm_value=50, requirement="Done"))
    downstream = task_repo.create_task(TaskCreate(title="Delivery", duration_min=30, llm_value=50, requirement="Done"))
    service = PriorityService(temp_db)
    before = service.calculate_priority(blocker.task_id)
    dep_repo.add_dependency(downstream.task_id, blocker.task_id)
    assert service.calculate_priority(blocker.task_id) == before + 1
    assert service.update_task_priority(blocker.task_id).priority_score == before + 1
    assert [task.task_id for task in service.get_top_priorities()] == [blocker.task_id]
    task_repo.update_task(downstream.task_id, TaskUpdate(status=TaskStatus.COMPLETED))
    assert service.calculate_priority(blocker.task_id) == before
    assert service.trend(blocker.task_id) == "falling"
    assert service.get_top_priorities()[0].priority_score == before


def test_actionable_ranking_inherits_downstream_priority(temp_db):
    with get_connection(temp_db) as conn:
        root, middle = _insert_tasks(conn, 2, urgency=1, importance=1, effort=5)
        urgent = _insert_tasks(conn, urgency=5, importance=5, effort=1)[0]
        independent = _insert_tasks(conn)[0]
        closed = _insert_tasks(conn, urgency=5, importance=5, effort=1, status="cancelled")[0]
        _edge(conn, middle, root)
        _edge(conn, urgent, middle)
        _edge(conn, closed, independent)
        conn.commit()
    service = PriorityService(temp_db)
    assert service.calculate_priority(root) == 1
    assert service.calculate_effective_priorities()[root] == 80
    assert service.calculate_effective_priorities()[middle] == 80
    assert [task.task_id for task in service.get_top_priorities()] == [root, independent]
    assert service.explain(root)["effective_score"] == 80
    assert service.get_top_priorities(limit=1)[0].task_id == root
    assert service.get_top_priorities(limit=0) == []
    with pytest.raises(ValueError, match="nonnegative"):
        service.get_top_priorities(limit=-1)


def test_status_filter_and_closed_task_calculation(temp_db):
    with get_connection(temp_db) as conn:
        active = _insert_tasks(conn)[0]
        closed = _insert_tasks(conn, status="completed")[0]
        conn.commit()
    service = PriorityService(temp_db)
    assert service.calculate_all_priorities() == {active: 40}
    assert service.calculate_all_priorities(TaskStatus.COMPLETED) == {closed: 40}
    assert service.calculate_priority(closed) == 40
    assert service.update_all_priorities(TaskStatus.COMPLETED) == 1
    assert service.calculate_effective_priorities(TaskStatus.COMPLETED) == {closed: 40}


def test_history_records_only_changed_scores_and_reads_are_pure(temp_db, monkeypatch):
    with get_connection(temp_db) as conn:
        task_id = _insert_tasks(conn)[0]
        conn.commit()
    service = PriorityService(temp_db)
    assert service.update_all_priorities() == 1
    assert service.update_all_priorities() == 0
    timestamp = service.update_task_priority(task_id).priority_updated_at
    assert service.trend(task_id) == "stable"
    for _ in range(3):
        service.calculate_priority(task_id)
        service.calculate_all_priorities()
        service.get_top_priorities()
        service.explain(task_id)
    assert len(service.history(task_id)) == 1
    monkeypatch.setattr(priority_service, "_now", lambda: NOW + timedelta(days=3))
    assert service.update_task_priority(task_id).priority_updated_at != timestamp
    assert service.trend(task_id) == "rising"
    assert [event["score"] for event in service.history(task_id)] == [40, 41]
    monkeypatch.setattr(priority_service, "_now", lambda: NOW)
    service.update_task_priority(task_id)
    assert service.trend(task_id) == "falling"


def test_custom_weights_persist_and_refresh_scores(temp_db):
    with get_connection(temp_db) as conn:
        task_id = _insert_tasks(conn, urgency=5)[0]
        conn.commit()
    weights = PriorityWeights(urgency=1, importance=0, effort=0, dependencies=0, age=0)
    PriorityService(temp_db, weights)
    service = PriorityService(temp_db)
    assert service.weights == weights
    assert service.calculate_priority(task_id) == 100
    assert service.explain(task_id)["preference_source"] == "custom"
    assert service.history(task_id)[-1]["score"] == 100


def test_refresh_uses_callers_transaction_and_rolls_back(temp_db):
    with get_connection(temp_db) as conn:
        task_id = _insert_tasks(conn)[0]
        conn.commit()
        assert refresh_priorities(conn) == 1
        conn.rollback()
    assert PriorityService(temp_db).history(task_id) == []
    with get_connection(temp_db) as conn:
        assert conn.execute("SELECT priority_score FROM tasks WHERE task_id=?", (str(task_id),)).fetchone()[0] is None


def test_completion_snapshot_preserves_normalized_factors(temp_db):
    with get_connection(temp_db) as conn:
        task_id = _insert_tasks(conn, urgency=5, importance=1, effort=2, created_at=NOW - timedelta(days=15))[0]
        downstream = _insert_tasks(conn)[0]
        _edge(conn, downstream, task_id)
        snapshot = completion_priority_factors(conn, task_id)
    assert snapshot == {"urgency": 1, "importance": 0, "effort": 0.75, "dependencies": 0.1, "age": 0.5}


def test_learning_requires_twenty_valid_completed_snapshots(temp_db):
    factors: dict[str, float] = dict.fromkeys(FACTOR_NAMES, 0.0)
    factors["urgency"] = 1.0
    with get_connection(temp_db) as conn:
        ids = _insert_tasks(conn, 27, status="completed")
        for task_id in ids[:19]:
            _completion(conn, task_id, json.dumps(factors))
        for task_id, invalid in zip(ids[19:25], [None, "bad", "[]", "{}", '{"urgency":true}', "null"], strict=True):
            _completion(conn, task_id, invalid)
        _completion(conn, ids[25], json.dumps(factors), status="cancelled")
        refresh_priorities(conn)
        assert conn.execute("SELECT COUNT(*) FROM priority_preferences").fetchone()[0] == 0
        _completion(conn, ids[26], json.dumps(factors))
        refresh_priorities(conn)
        conn.commit()
    service = PriorityService(temp_db)
    assert service.weights.urgency > PriorityWeights().urgency
    assert abs(service.weights.urgency - PriorityWeights().urgency) < 0.03
    with get_connection(temp_db) as conn:
        row = conn.execute("SELECT source,sample_count FROM priority_preferences").fetchone()
        assert dict(row) == {"source": "learned", "sample_count": 20}
        before = service.weights
        refresh_priorities(conn)
        conn.commit()
    assert service.weights == before


def test_learning_recomputes_replaced_completion_evidence_at_same_count(temp_db, completion_repo):
    original = {**dict.fromkeys(FACTOR_NAMES, 0.0), "urgency": 1.0}
    corrected = {**dict.fromkeys(FACTOR_NAMES, 0.0), "importance": 1.0}
    with get_connection(temp_db) as conn:
        completed = _insert_tasks(conn, 20, status="completed")
        active = _insert_tasks(conn, urgency=5, importance=1, effort=5, created_at=NOW + timedelta(days=1))[0]
        for task_id in completed:
            _completion(conn, task_id, json.dumps(original))
        conn.commit()
    service = PriorityService(temp_db)
    assert service.update_all_priorities() == 1
    before = service.weights
    old = completion_repo.get_completion_by_task_id(completed[-1])
    assert old is not None
    completion_repo.delete_completion(old.completion_id)
    completion_repo.create_completion(
        CompletionCreate(
            task_id=completed[-1],
            status=CompletionStatus.COMPLETED,
            duration_expected=30,
            duration_actual=30,
            closed_at=NOW,
            priority_factors=corrected,
        )
    )
    after = service.weights
    assert after.urgency < before.urgency
    assert after.importance > before.importance
    assert service.calculate_priority(active) == round(100 * after.urgency, 1)
    with get_connection(temp_db) as conn:
        preference = dict(conn.execute("SELECT * FROM priority_preferences").fetchone())
        assert preference["source"] == "learned"
        assert preference["sample_count"] == 20
        assert preference["updated_at"] == NOW.isoformat()
        assert conn.execute("SELECT COUNT(*) FROM completion").fetchone()[0] == 20
        assert conn.execute("SELECT priority_score FROM tasks WHERE task_id=?", (str(active),)).fetchone()[0] == round(
            100 * after.urgency, 1
        )
    assert service.update_all_priorities() == 0
    with get_connection(temp_db) as conn:
        assert dict(conn.execute("SELECT * FROM priority_preferences").fetchone()) == preference


def test_learning_updates_evidence_count_even_when_weights_are_unchanged(temp_db, monkeypatch):
    factors = json.dumps(dict.fromkeys(FACTOR_NAMES, 0.5))
    with get_connection(temp_db) as conn:
        ids = _insert_tasks(conn, 21, status="completed")
        for task_id in ids[:20]:
            _completion(conn, task_id, factors)
        refresh_priorities(conn)
        before = dict(conn.execute("SELECT * FROM priority_preferences").fetchone())
        monkeypatch.setattr(priority_service, "_now", lambda: NOW + timedelta(hours=1))
        _completion(conn, ids[-1], factors)
        refresh_priorities(conn)
        after = dict(conn.execute("SELECT * FROM priority_preferences").fetchone())
        assert after["weights"] == before["weights"]
        assert after["sample_count"] == 21
        assert after["updated_at"] == (NOW + timedelta(hours=1)).isoformat()
        monkeypatch.setattr(priority_service, "_now", lambda: NOW + timedelta(hours=2))
        refresh_priorities(conn)
        assert dict(conn.execute("SELECT * FROM priority_preferences").fetchone()) == after


def test_invalid_snapshot_values_and_custom_weights_are_not_learned(temp_db):
    valid = dict.fromkeys(FACTOR_NAMES, 0.5)
    with get_connection(temp_db) as conn:
        ids = _insert_tasks(conn, 27, status="completed")
        for task_id in ids[:20]:
            _completion(conn, task_id, json.dumps(valid))
        for task_id, value in zip(ids[20:], [float("nan"), float("inf"), -1, True, 2, "unknown", 10**400], strict=True):
            _completion(conn, task_id, json.dumps({**valid, "age": value}))
        refresh_priorities(conn)
        preference = conn.execute("SELECT sample_count FROM priority_preferences").fetchone()
        assert preference["sample_count"] == 20
        conn.commit()
    weights = PriorityWeights(urgency=1, importance=0, effort=0, dependencies=0, age=0)
    service = PriorityService(temp_db, weights)
    service.update_all_priorities()
    assert service.weights == weights
    with get_connection(temp_db) as conn:
        before = dict(conn.execute("SELECT * FROM priority_preferences").fetchone())
        conn.execute(
            "UPDATE completion SET priority_factors=? WHERE task_id=?",
            (json.dumps({**valid, "urgency": 1.0}), str(ids[19])),
        )
        conn.commit()
    service.update_all_priorities()
    assert service.weights == weights
    with get_connection(temp_db) as conn:
        assert dict(conn.execute("SELECT * FROM priority_preferences").fetchone()) == before


def test_missing_tasks_raise_without_side_effects(temp_db):
    service = PriorityService(temp_db)
    missing = uuid4()
    for operation in [
        service.calculate_priority,
        service.update_task_priority,
        service.explain,
        service.history,
        service.trend,
    ]:
        with pytest.raises(TaskNotFoundError):
            operation(missing)
    with get_connection(temp_db) as conn, pytest.raises(TaskNotFoundError):
        completion_priority_factors(conn, missing)


def test_corrupt_cycles_fail_explicitly(temp_db):
    with get_connection(temp_db) as conn:
        first, second = _insert_tasks(conn, 2)
        _edge(conn, first, second)
        _edge(conn, second, first)
        conn.commit()
    with pytest.raises(DependencyError, match="cyclic"):
        PriorityService(temp_db).get_top_priorities()


def test_thousand_scores_use_fixed_query_count(temp_db, monkeypatch):
    with get_connection(temp_db) as conn:
        ids = _insert_tasks(conn, 1000)
        conn.commit()
    queries = []

    @contextmanager
    def traced_connection(db_path):
        with get_connection(db_path) as conn:
            conn.set_trace_callback(queries.append)
            yield conn

    monkeypatch.setattr(priority_service, "get_connection", traced_connection)
    scores = PriorityService(temp_db).calculate_all_priorities()
    assert set(scores) == set(ids)
    assert set(scores.values()) == {40}
    assert len([query for query in queries if query.startswith("SELECT")]) == 3


def test_thousand_skill_matches_use_one_additional_snapshot_query(temp_db, monkeypatch):
    with get_connection(temp_db) as conn:
        ids = _insert_tasks(conn, 1000)
        conn.execute("UPDATE tasks SET skill_domain='python',required_skill_level=3")
        conn.execute(
            "INSERT INTO skill_assessments(assessment_id,domain,level,evidence,assessed_at,recorded_at) "
            "VALUES(?,?,?,?,?,?)",
            (str(uuid4()), "python", 3, "Built maintained tools", NOW.isoformat(), NOW.isoformat()),
        )
        conn.commit()
    queries = []

    @contextmanager
    def traced_connection(db_path):
        with get_connection(db_path) as conn:
            conn.set_trace_callback(queries.append)
            yield conn

    monkeypatch.setattr(priority_service, "get_connection", traced_connection)
    monkeypatch.setattr(planning, "get_connection", traced_connection)
    selected = PriorityService(temp_db).get_top_priorities(limit=1000, match_skills=True)
    assert {task.task_id for task in selected} == set(ids)
    assert len([query for query in queries if query.startswith("SELECT")]) == 4
    assert len([query for query in queries if "FROM skill_assessments" in query]) == 1


def test_deep_dag_ranking_is_iterative(temp_db):
    with get_connection(temp_db) as conn:
        ids = _insert_tasks(conn, 1100, urgency=1, importance=1, effort=5)
        conn.executemany(
            "INSERT INTO task_dependencies(dependency_id,task_id,blocker_id,created_at) VALUES(?,?,?,?)",
            [(str(uuid4()), str(downstream), str(blocker), NOW.isoformat()) for blocker, downstream in pairwise(ids)],
        )
        conn.execute("UPDATE tasks SET urgency=5,importance=5,effort=1 WHERE task_id=?", (str(ids[-1]),))
        conn.commit()
    service = PriorityService(temp_db)
    assert service.calculate_effective_priorities()[ids[0]] == 80
    assert [task.task_id for task in service.get_top_priorities()] == [ids[0]]


def test_skill_filter_requires_evidenced_readiness(temp_db):
    with get_connection(temp_db) as conn:
        unrestricted, unknown, assessed = _insert_tasks(conn, 3)
        conn.execute("UPDATE tasks SET skill_domain='unknown',required_skill_level=3 WHERE task_id=?", (str(unknown),))
        conn.execute("UPDATE tasks SET skill_domain='python',required_skill_level=3 WHERE task_id=?", (str(assessed),))
        conn.execute(
            "INSERT INTO skill_assessments(assessment_id,domain,level,evidence,assessed_at,recorded_at) "
            "VALUES(?,?,?,?,?,?)",
            (str(uuid4()), "python", 4, "Delivered tested parser", NOW.isoformat(), NOW.isoformat()),
        )
        conn.commit()
    selected = PriorityService(temp_db).get_top_priorities(match_skills=True)
    assert {task.task_id for task in selected} == {unrestricted, assessed}


def test_skill_filter_cannot_mix_old_requirement_with_new_assessment(temp_db, monkeypatch):
    with get_connection(temp_db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        task_id = _insert_tasks(conn)[0]
        conn.execute("UPDATE tasks SET skill_domain='python',required_skill_level=3 WHERE task_id=?", (str(task_id),))
        conn.execute(
            "INSERT INTO skill_assessments(assessment_id,domain,level,evidence,assessed_at,recorded_at) "
            "VALUES(?,?,?,?,?,?)",
            (str(uuid4()), "python", 2, "Beginning practice", NOW.isoformat(), NOW.isoformat()),
        )
        conn.commit()
    service = PriorityService(temp_db)
    assert service.get_top_priorities(match_skills=True) == []
    wrote = False

    def raise_requirement_then_skill(query):
        nonlocal wrote
        if not wrote and "FROM skill_assessments" in query:
            with get_connection(temp_db) as writer:
                writer.execute("UPDATE tasks SET required_skill_level=5 WHERE task_id=?", (str(task_id),))
                writer.commit()
                writer.execute(
                    "INSERT INTO skill_assessments(assessment_id,domain,level,evidence,assessed_at,recorded_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        str(uuid4()),
                        "python",
                        3,
                        "More practice",
                        (NOW + timedelta(days=1)).isoformat(),
                        (NOW + timedelta(days=1)).isoformat(),
                    ),
                )
                writer.commit()
            wrote = True

    @contextmanager
    def concurrent_connection(db_path):
        with get_connection(db_path) as conn:
            conn.set_trace_callback(raise_requirement_then_skill)
            yield conn

    monkeypatch.setattr(priority_service, "get_connection", concurrent_connection)
    monkeypatch.setattr(planning, "get_connection", concurrent_connection)
    assert service.get_top_priorities(match_skills=True) == []
    assert wrote
    latest = planning.PlanningService(temp_db).match(task_id)
    assert (latest.required_level, latest.known_level, latest.ready) == (5, 3, False)
    assert service.get_top_priorities(match_skills=True) == []


def test_empty_database_and_empty_history(temp_db):
    service = PriorityService(temp_db)
    assert service.calculate_all_priorities() == {}
    assert service.calculate_effective_priorities() == {}
    assert service.get_top_priorities() == []
    assert service.update_all_priorities() == 0


def test_calculation_reads_consistent_snapshot_during_concurrent_update(temp_db, monkeypatch):
    with get_connection(temp_db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        root = _insert_tasks(conn, urgency=1, importance=1, effort=5)[0]
        downstream = _insert_tasks(conn)[0]
        conn.commit()
    wrote = False

    def write_during_dependency_read(query):
        nonlocal wrote
        if not wrote and query.startswith("SELECT d.task_id"):
            wrote = True
            with get_connection(temp_db) as writer:
                writer.execute("UPDATE tasks SET urgency=5 WHERE task_id=?", (str(root),))
                _edge(writer, downstream, root)
                writer.commit()

    @contextmanager
    def concurrent_connection(db_path):
        with get_connection(db_path) as conn:
            conn.set_trace_callback(write_during_dependency_read)
            yield conn

    monkeypatch.setattr(priority_service, "get_connection", concurrent_connection)
    service = PriorityService(temp_db)
    assert service.calculate_all_priorities()[root] == 0
    assert wrote
    assert service.calculate_all_priorities()[root] == 31


@pytest.mark.parametrize("removal", ["completion", "task"])
def test_removing_learning_evidence_restores_defaults(temp_db, completion_repo, task_repo, removal):
    factors = json.dumps({**dict.fromkeys(FACTOR_NAMES, 0.0), "urgency": 1.0})
    with get_connection(temp_db) as conn:
        completed = _insert_tasks(conn, 20, status="completed")
        active = _insert_tasks(conn, urgency=5, importance=1, effort=5, created_at=NOW + timedelta(days=1))[0]
        for task_id in completed:
            _completion(conn, task_id, factors)
        conn.commit()
    service = PriorityService(temp_db)
    service.update_all_priorities()
    assert service.calculate_priority(active) > 30
    if removal == "task":
        task_repo.delete_task(completed[-1])
    else:
        event = completion_repo.get_completion_by_task_id(completed[-1])
        assert event is not None
        completion_repo.delete_completion(event.completion_id)
    assert service.weights == PriorityWeights()
    assert service.calculate_priority(active) == 30
    stored = task_repo.get_task(active)
    assert stored is not None
    assert stored.priority_score == 30
    assert service.explain(active)["preference_source"] == "default"


def test_historical_completion_crosses_learning_threshold_atomically(temp_db, completion_repo, task_repo):
    factors = {**dict.fromkeys(FACTOR_NAMES, 0.0), "urgency": 1.0}
    with get_connection(temp_db) as conn:
        completed = _insert_tasks(conn, 20, status="completed")
        active = _insert_tasks(conn, urgency=5, importance=1, effort=5, created_at=NOW + timedelta(days=1))[0]
        for task_id in completed[:-1]:
            _completion(conn, task_id, json.dumps(factors))
        conn.commit()
    service = PriorityService(temp_db)
    service.update_all_priorities()
    assert service.weights == PriorityWeights()
    completion_repo.create_completion(
        CompletionCreate(
            task_id=completed[-1],
            status=CompletionStatus.COMPLETED,
            duration_expected=30,
            duration_actual=30,
            priority_factors=factors,
        )
    )
    assert service.weights.urgency > 0.30
    stored = task_repo.get_task(active)
    assert stored is not None
    assert stored.priority_score == service.calculate_priority(active)
