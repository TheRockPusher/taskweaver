"""Tests for agent tools."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.memory import MemoryService
from taskweaver.agents.tools import (
    add_dependency_tool,
    assess_skill_tool,
    completion_insights_tool,
    create_goal_tool,
    create_task_tool,
    delete_goal_tool,
    estimate_duration_tool,
    forget_fact_tool,
    get_blocked_tool,
    get_blockers_tool,
    get_task_details_tool,
    goal_progress_tool,
    link_task_goal_tool,
    list_facts_tool,
    list_goals_tool,
    list_skills_tool,
    list_tasks_tool,
    match_task_skills_tool,
    priority_weights_tool,
    rank_tasks_tool,
    recalculate_priorities_tool,
    recommendations_tool,
    remember_fact_tool,
    remove_dependency_tool,
    score_task_tool,
    search_facts_tool,
    search_tasks_tool,
    skill_history_tool,
    update_fact_tool,
    update_goal_tool,
    update_task_status_tool,
    update_task_tool,
)
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import get_connection, init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.models import Task, TaskCreate, TaskStatus
from taskweaver.database.priority_service import PriorityWeights
from taskweaver.database.repository import TaskRepository


@pytest.fixture
def deps(db_path: Path) -> TaskDependencies:
    """Create TaskDependencies with repositories."""
    init_database(db_path)
    return TaskDependencies(
        task_repo=TaskRepository(db_path),
        dep_repo=TaskDependencyRepository(db_path),
        completion_repo=CompletionRepository(db_path),
        memories="",
        user_id="test_user",
    )


@pytest.fixture
def ctx(deps: TaskDependencies) -> RunContext[TaskDependencies]:
    """Create mock RunContext with dependencies."""

    class MockContext:
        def __init__(self, dependencies: TaskDependencies):
            self.deps = dependencies

    return MockContext(deps)  # type: ignore[return-value]


@pytest.fixture
def sample_task(deps: TaskDependencies) -> Task:
    """Create a sample task for testing."""
    task_data = TaskCreate(
        title="Test Task",
        description="Test description",
        duration_min=60,
        llm_value=75.0,
        requirement="Must work",
    )
    return deps.task_repo.create_task(task_data)


class TestUpdateTaskTool:
    """Tests for update_task_tool."""

    def test_update_task_success(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test updating task with valid data."""
        result = update_task_tool(ctx, sample_task.task_id, {"title": "Updated Title", "duration_min": 90})

        assert result.title == "Updated Title"
        assert result.duration_min == 90
        assert result.task_id == sample_task.task_id

    def test_update_task_status(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test updating task status."""
        result = update_task_tool(ctx, sample_task.task_id, {"status": "in_progress"})

        assert result.status is TaskStatus.IN_PROGRESS

    def test_update_task_not_found(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test update with non-existent task raises ModelRetry."""
        fake_id = uuid4()
        with pytest.raises(ModelRetry):
            update_task_tool(ctx, fake_id, {"title": "New Title"})

    def test_update_task_invalid_status(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test update with invalid status raises ModelRetry."""
        with pytest.raises(ModelRetry):
            update_task_tool(ctx, sample_task.task_id, {"status": "invalid_status"})


class TestListTasksTool:
    """Tests for list_tasks_tool (backward compatibility)."""

    def test_list_all_tasks(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test listing all tasks returns concise format by default."""
        result = list_tasks_tool(ctx)

        assert isinstance(result, str)
        assert "Found 1 task" in result
        assert sample_task.title in result
        assert f"Status: {sample_task.status.value}" in result
        assert "TaskStatus." not in result

    def test_list_tasks_by_status(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:  # noqa: ARG002
        """Test listing tasks filtered by status."""
        result = list_tasks_tool(ctx, status="pending", response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["status"] == "pending"

    def test_list_tasks_empty_filter(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test listing with filter that matches no tasks."""
        task_data = TaskCreate(
            title="Test Task",
            duration_min=30,
            llm_value=50.0,
            requirement="Requirement",
        )
        task = ctx.deps.task_repo.create_task(task_data)
        ctx.deps.task_repo.mark_completed(task.task_id)

        result = list_tasks_tool(ctx, status="pending")

        assert isinstance(result, str)
        assert "No tasks found" in result

    def test_list_tasks_multiple(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test listing multiple tasks."""
        for i in range(3):
            ctx.deps.task_repo.create_task(
                TaskCreate(
                    title=f"Task {i}",
                    duration_min=30,
                    llm_value=50.0,
                    requirement=f"Req {i}",
                )
            )

        result = list_tasks_tool(ctx, response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) == 3


class TestGetTaskDetailsTool:
    """Tests for get_task_details_tool."""

    def test_get_existing_task(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test retrieving existing task details."""
        result = get_task_details_tool(ctx, sample_task.task_id)

        assert isinstance(result, Task)
        assert result.task_id == sample_task.task_id
        assert result.title == sample_task.title

    def test_get_nonexistent_task(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test retrieving non-existent task raises ModelRetry."""
        fake_id = uuid4()

        with pytest.raises(ModelRetry, match="not found"):
            get_task_details_tool(ctx, fake_id)


class TestListTasksPagination:
    """Tests for list_tasks_tool pagination."""

    def test_pagination_first_page(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test first page returns correct limit."""
        # Create 25 tasks
        for i in range(25):
            ctx.deps.task_repo.create_task(
                TaskCreate(title=f"Task {i}", duration_min=30, llm_value=50.0, requirement=f"Req {i}")
            )

        result = list_tasks_tool(ctx, limit=10, offset=0, response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) == 10
        assert result["total_count"] == 25
        assert result["has_more"] is True

    def test_pagination_last_page(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test last page has fewer results."""
        for i in range(25):
            ctx.deps.task_repo.create_task(
                TaskCreate(title=f"Task {i}", duration_min=30, llm_value=50.0, requirement=f"Req {i}")
            )

        result = list_tasks_tool(ctx, limit=10, offset=20, response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) == 5
        assert result["has_more"] is False

    def test_max_limit_enforced(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test limit capped at 50."""
        for i in range(60):
            ctx.deps.task_repo.create_task(
                TaskCreate(title=f"Task {i}", duration_min=30, llm_value=50.0, requirement=f"Req {i}")
            )

        result = list_tasks_tool(ctx, limit=100, response_format="detailed")

        assert isinstance(result, dict)
        assert len(result["tasks"]) <= 50

    def test_invalid_sort_by_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test invalid sort_by raises ModelRetry."""
        with pytest.raises(ModelRetry, match="Invalid sort_by"):
            list_tasks_tool(ctx, sort_by="invalid")

    def test_invalid_response_format_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test invalid response_format raises ModelRetry."""
        with pytest.raises(ModelRetry, match="Invalid response_format"):
            list_tasks_tool(ctx, response_format="xml")


class TestSearchTasksTool:
    """Tests for search_tasks_tool."""

    def test_search_by_title(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test searching tasks by title keyword."""
        ctx.deps.task_repo.create_task(
            TaskCreate(title="Build login feature", duration_min=120, llm_value=80.0, requirement="OAuth2")
        )
        ctx.deps.task_repo.create_task(
            TaskCreate(title="Fix logout bug", duration_min=30, llm_value=60.0, requirement="Session")
        )

        result = search_tasks_tool(ctx, "login", response_format="detailed")

        assert isinstance(result, dict)
        assert result["total_matches"] == 1
        assert "login" in result["tasks"][0]["title"].lower()

    def test_search_by_requirement(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test searching tasks by requirement field."""

        ctx.deps.task_repo.create_task(
            TaskCreate(title="Setup auth", duration_min=60, llm_value=75.0, requirement="OAuth2 implementation")
        )

        result = search_tasks_tool(ctx, "OAuth2", response_format="detailed")

        assert isinstance(result, dict)
        assert result["total_matches"] == 1

    def test_search_concise_status(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Search summaries expose the status value, not the enum representation."""
        result = search_tasks_tool(ctx, sample_task.title, status="pending")

        assert isinstance(result, str)
        assert f"Status: {sample_task.status.value}" in result
        assert "TaskStatus." not in result

    def test_search_no_matches(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test search with no matching tasks."""

        ctx.deps.task_repo.create_task(
            TaskCreate(title="Build feature", duration_min=60, llm_value=70.0, requirement="Test")
        )

        result = search_tasks_tool(ctx, "nonexistent", response_format="concise")

        assert isinstance(result, str)
        assert "No tasks found" in result

    def test_search_empty_query_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test empty query raises ModelRetry."""

        with pytest.raises(ModelRetry, match="cannot be empty"):
            search_tasks_tool(ctx, "")

    def test_search_with_min_priority(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test search with priority filter."""

        ctx.deps.task_repo.create_task(
            TaskCreate(title="High priority task", duration_min=30, llm_value=90.0, requirement="Test")
        )
        ctx.deps.task_repo.create_task(
            TaskCreate(title="Low priority task", duration_min=120, llm_value=30.0, requirement="Test")
        )

        result = search_tasks_tool(ctx, "task", min_priority=2.0, response_format="detailed")

        assert isinstance(result, dict)
        assert result["total_matches"] == 1
        assert result["tasks"][0]["llm_value"] / result["tasks"][0]["duration_min"] >= 2.0


class TestUpdateTaskStatusTool:
    """Tests for consolidated update_task_status_tool."""

    def test_mark_in_progress(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test marking task as in_progress."""

        result = update_task_status_tool(ctx, sample_task.task_id, "in_progress")

        assert "in progress" in result.lower()
        task = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert task is not None
        assert task.status == TaskStatus.IN_PROGRESS

    def test_mark_completed_without_tracking(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test marking task completed without duration."""

        result = update_task_status_tool(ctx, sample_task.task_id, "completed")

        assert "completed" in result.lower()
        completion = ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id)
        assert completion is None

    def test_mark_completed_with_tracking(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test marking task completed with duration tracking."""

        result = update_task_status_tool(ctx, sample_task.task_id, "completed", duration_actual=90)

        assert "90min actual" in result
        assert "variance" in result.lower()
        completion = ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id)
        assert completion is not None
        assert completion.duration_actual == 90

    def test_mark_cancelled(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test marking task cancelled."""

        result = update_task_status_tool(ctx, sample_task.task_id, "cancelled")

        assert "cancelled" in result.lower()
        task = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert task is not None
        assert task.status == TaskStatus.CANCELLED

    def test_invalid_status_raises(self, ctx: RunContext[TaskDependencies], sample_task: Task) -> None:
        """Test invalid status raises ModelRetry."""

        with pytest.raises(ModelRetry, match="Invalid new_status"):
            update_task_status_tool(ctx, sample_task.task_id, "invalid")

    def test_nonexistent_task_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test non-existent task raises ModelRetry."""

        with pytest.raises(ModelRetry, match="not found"):
            update_task_status_tool(ctx, uuid4(), "completed")

    @pytest.mark.parametrize("status", ["completed", "cancelled"])
    def test_tracked_closure_snapshots_dependencies(
        self, ctx: RunContext[TaskDependencies], sample_task: Task, status: str
    ) -> None:
        """The consolidated tool captures blocker evidence before cleanup."""
        downstream = ctx.deps.task_repo.create_task(
            TaskCreate(title="Downstream", duration_min=30, llm_value=80.0, requirement="Needs sample task")
        )
        ctx.deps.dep_repo.add_dependency(downstream.task_id, sample_task.task_id)

        update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90, conclusion="Measured time")

        completion = ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id)
        assert completion is not None
        assert completion.status.value == status
        assert completion.duration_actual == 90
        assert completion.duration_expected == sample_task.duration_min
        assert completion.raw_duration_min == sample_task.raw_duration_min
        assert completion.category == sample_task.category
        assert completion.conclusion == "Measured time"
        assert completion.priority_factors is not None
        assert completion.priority_factors["dependencies"] > 0
        assert ctx.deps.dep_repo.get_blockers(downstream.task_id) == []

    @pytest.mark.parametrize("status", ["completed", "cancelled"])
    def test_tracked_closure_failure_preserves_task_and_edges(
        self, ctx: RunContext[TaskDependencies], sample_task: Task, status: str
    ) -> None:
        """Cleanup failures propagate and roll back the complete closure transaction."""
        downstream = ctx.deps.task_repo.create_task(
            TaskCreate(title="Downstream", duration_min=30, llm_value=80.0, requirement="Needs sample task")
        )
        ctx.deps.dep_repo.add_dependency(downstream.task_id, sample_task.task_id)
        with get_connection(ctx.deps.task_repo.db_path) as conn, conn:
            conn.execute(
                """CREATE TRIGGER reject_cleanup BEFORE DELETE ON task_dependencies
                   BEGIN SELECT RAISE(ABORT, 'cleanup refused'); END"""
            )

        with pytest.raises(sqlite3.IntegrityError, match="cleanup refused"):
            update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90)

        unchanged = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert unchanged is not None
        assert unchanged.status == TaskStatus.PENDING
        assert ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id) is None
        assert [task.task_id for task in ctx.deps.dep_repo.get_blockers(downstream.task_id)] == [sample_task.task_id]

    @pytest.mark.parametrize("status", ["completed", "cancelled"])
    def test_completion_retries_are_idempotent_and_conflicts_become_model_retry(
        self, ctx: RunContext[TaskDependencies], sample_task: Task, status: str
    ) -> None:
        """Correct retries reuse evidence; conflicting requests never rewrite it."""
        update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90, conclusion="Measured time")
        original = ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id)
        assert original is not None

        update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90, conclusion="Measured time")
        assert ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id) == original

        with pytest.raises(ModelRetry, match="Conflicting completion"):
            update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=100, conclusion="Measured time")
        with pytest.raises(ModelRetry, match="Conflicting completion"):
            update_task_status_tool(ctx, sample_task.task_id, status, duration_actual=90, conclusion="Changed notes")
        other_status = "cancelled" if status == "completed" else "completed"
        with pytest.raises(ModelRetry, match="different status"):
            update_task_status_tool(
                ctx, sample_task.task_id, other_status, duration_actual=90, conclusion="Measured time"
            )

        assert ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id) == original
        closed = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert closed is not None
        assert closed.status.value == status

    @pytest.mark.parametrize("status", ["completed", "cancelled"])
    def test_untracked_closure_creates_no_completion_evidence(
        self, ctx: RunContext[TaskDependencies], sample_task: Task, status: str
    ) -> None:
        """A closure without measured time changes status without inventing evidence."""
        update_task_status_tool(ctx, sample_task.task_id, status, conclusion="No measured time")

        closed = ctx.deps.task_repo.get_task(sample_task.task_id)
        assert closed is not None
        assert closed.status.value == status
        assert ctx.deps.completion_repo.get_completion_by_task_id(sample_task.task_id) is None


def test_goal_and_task_nullable_updates_preserve_omission(ctx: RunContext[TaskDependencies]) -> None:
    """Goal edits, field updates and deletion preserve work and immutable raw estimates."""
    goal = create_goal_tool(ctx, "Launch", "Public release")
    goal_id = UUID(goal["goal_id"])
    created = create_task_tool(
        ctx,
        "Build release",
        30,
        90,
        "Publish artifact",
        description="Keep this",
        urgency=5,
        importance=4,
        effort=2,
        category="release",
        goal_id=goal_id,
        skill_domain="packaging",
        required_skill_level=3,
    )
    task_id = UUID(created["task_id"])
    update_goal_tool(ctx, goal_id, title="Launch product")
    assert list_goals_tool(ctx)[0]["goal"]["description"] == "Public release"
    changed = update_task_tool(ctx, task_id, {"title": "Release product", "duration_min": 45})
    assert changed.description == "Keep this"
    assert changed.goal_id == goal_id
    assert changed.skill_domain == "packaging"
    assert changed.required_skill_level == 3
    assert changed.raw_duration_min == 30
    assert changed.urgency == 5
    changed = update_task_tool(
        ctx,
        task_id,
        {"description": None, "skill_domain": None, "required_skill_level": None},
    )
    assert changed.description is None
    assert changed.skill_domain is None
    assert changed.required_skill_level is None
    assert goal_progress_tool(ctx, goal_id)["total"] == 1
    update_goal_tool(ctx, goal_id, replace_description=True)
    assert list_goals_tool(ctx)[0]["goal"]["description"] is None
    with pytest.raises(ModelRetry, match="Goal not found"):
        update_task_tool(ctx, task_id, {"goal_id": uuid4(), "title": "Must not apply"})
    assert get_task_details_tool(ctx, task_id).title == "Release product"
    assert link_task_goal_tool(ctx, task_id, None)["goal_id"] is None
    link_task_goal_tool(ctx, task_id, goal_id)
    update_task_status_tool(ctx, task_id, "completed")
    assert goal_progress_tool(ctx, goal_id)["fraction"] == 1
    cancelled = create_task_tool(ctx, "Obsolete", 10, 20, "Not needed", goal_id=goal_id)
    update_task_status_tool(ctx, UUID(cancelled["task_id"]), "cancelled")
    progress = goal_progress_tool(ctx, goal_id)
    assert (progress["completed"], progress["total"], progress["cancelled"]) == (1, 1, 1)
    delete_goal_tool(ctx, goal_id)
    assert get_task_details_tool(ctx, task_id).goal_id is None
    assert get_task_details_tool(ctx, task_id).status is TaskStatus.COMPLETED
    with pytest.raises(ModelRetry, match="Goal not found"):
        goal_progress_tool(ctx, goal_id)


def test_priority_tools_refresh_and_rank_actionable_inherited_scores(ctx: RunContext[TaskDependencies]) -> None:
    """Rankings use MCDA inheritance, not CD3, and history reflects real factor/weight changes."""
    blocker = create_task_tool(ctx, "Small prerequisite", 120, 10, "Unblock", urgency=1, importance=1, effort=5)
    downstream = create_task_tool(ctx, "Urgent delivery", 30, 90, "Deliver", urgency=5, importance=5, effort=1)
    standalone = create_task_tool(ctx, "Routine", 1, 100, "Routine", urgency=2, importance=2, effort=4)
    blocker_id, downstream_id = UUID(blocker["task_id"]), UUID(downstream["task_id"])
    add_dependency_tool(ctx, downstream_id, blocker_id)
    explanation = score_task_tool(ctx, blocker_id)
    assert explanation["effective_score"] > explanation["score"]
    assert explanation["components"]["dependencies"]["raw"] == 1
    assert explanation["score"] == round(sum(c["contribution"] for c in explanation["components"].values()), 1)
    ranked = rank_tasks_tool(ctx)
    assert [task["task_id"] for task in ranked] == [blocker["task_id"], standalone["task_id"]]
    update_task_tool(ctx, blocker_id, {"urgency": 5, "importance": 5, "effort": 1})
    assert score_task_tool(ctx, blocker_id)["trend"] == "rising"
    weights = PriorityWeights(urgency=1, importance=0, effort=0, dependencies=0, age=0)
    priority_weights_tool(ctx, weights)
    assert priority_weights_tool(ctx)["urgency"] == 1
    assert score_task_tool(ctx, blocker_id)["score"] == 100
    assert recalculate_priorities_tool(ctx)["changed"] == 0
    update_task_status_tool(ctx, blocker_id, "completed")
    assert get_blockers_tool(ctx, downstream_id) == []
    assert rank_tasks_tool(ctx)[0]["task_id"] == downstream["task_id"]
    with pytest.raises(ModelRetry, match="nonnegative"):
        rank_tasks_tool(ctx, limit=-1)
    with pytest.raises(ModelRetry, match="not found"):
        score_task_tool(ctx, uuid4())
    with pytest.raises(ModelRetry):
        recalculate_priorities_tool(ctx, status="invalid")


def test_skills_learning_gaps_and_dependency_exclusion(ctx: RunContext[TaskDependencies]) -> None:
    """Unknown/insufficient skills are learning gaps, not ready work; blockers exclude either bucket."""
    skill_task = create_task_tool(
        ctx,
        "Design schema",
        60,
        80,
        "Migration ready",
        skill_domain="sqlite",
        required_skill_level=3,
    )
    task_id = UUID(skill_task["task_id"])
    blocker = create_task_tool(ctx, "Access database", 10, 50, "Have access")
    blocker_id = UUID(blocker["task_id"])
    assert match_task_skills_tool(ctx, task_id)["known_level"] is None
    assert match_task_skills_tool(ctx, task_id)["learning_gap"] is True
    assert task_id not in {UUID(task["task_id"]) for task in rank_tasks_tool(ctx)}
    assert recommendations_tool(ctx)["learning_gaps"][0]["task_id"] == str(task_id)
    assess_skill_tool(ctx, "sqlite", 2, "Completed introductory exercises")
    assert match_task_skills_tool(ctx, task_id)["ready"] is False
    add_dependency_tool(ctx, task_id, blocker_id)
    assert match_task_skills_tool(ctx, task_id)["blocked"] is True
    assert recommendations_tool(ctx)["learning_gaps"] == []
    assert [task.task_id for task in get_blocked_tool(ctx, blocker_id)] == [task_id]
    remove_dependency_tool(ctx, task_id, blocker_id)
    assess_skill_tool(ctx, "sqlite", 3, "Independently shipped safe migration")
    assess_skill_tool(ctx, "sqlite", 1, "Historical first exercise", datetime.now(UTC) - timedelta(days=30))
    assert list_skills_tool(ctx)[0]["level"] == 3
    assert [entry["level"] for entry in skill_history_tool(ctx, "sqlite")] == [1, 2, 3]
    assert match_task_skills_tool(ctx, task_id)["ready"] is True
    assert task_id in {UUID(task["task_id"]) for task in recommendations_tool(ctx)["ready"]}
    assert task_id in {UUID(task["task_id"]) for task in rank_tasks_tool(ctx)}
    assess_skill_tool(ctx, "sqlite", 2, "Needs supervision after reassessment")
    assert match_task_skills_tool(ctx, task_id)["ready"] is False
    with pytest.raises(ModelRetry):
        assess_skill_tool(ctx, "sqlite", 6, "Invalid level")
    with pytest.raises(ModelRetry):
        assess_skill_tool(ctx, "sqlite", 3, " ")
    assert list_skills_tool(ctx)[0]["level"] == 2
    with pytest.raises(ModelRetry, match="not found"):
        get_blockers_tool(ctx, uuid4())
    update_task_status_tool(ctx, task_id, "cancelled")
    assert recommendations_tool(ctx)["learning_gaps"] == []
    assert task_id not in {UUID(task["task_id"]) for task in recommendations_tool(ctx)["ready"]}


def test_duration_tools_use_immutable_category_evidence(ctx: RunContext[TaskDependencies]) -> None:
    """Three actual/raw observations enable adjustment once; later task edits do not rewrite learning."""
    assert estimate_duration_tool(ctx, "coding", 30)["confidence"]["automatic_adjustment"] is False
    for index in range(3):
        task = create_task_tool(ctx, f"Measured {index}", 30, 50, "Done", category="coding")
        update_task_status_tool(ctx, UUID(task["task_id"]), "completed", duration_actual=60)
    estimate = estimate_duration_tool(ctx, "coding", 30)
    assert (estimate["adjusted_minutes"], estimate["multiplier"], estimate["sample_count"]) == (60, 2, 3)
    assert estimate["confidence"]["median_absolute_deviation"] == 0
    learned = create_task_tool(ctx, "Next task", 30, 50, "Done", category="coding")
    assert (learned["raw_duration_min"], learned["duration_min"]) == (30, 60)
    changed = update_task_tool(ctx, UUID(learned["task_id"]), {"duration_min": 90, "category": "review"})
    assert changed.raw_duration_min == 30
    cancelled = create_task_tool(ctx, "Cancelled", 30, 40, "Stopped", category="coding")
    update_task_status_tool(ctx, UUID(cancelled["task_id"]), "cancelled", duration_actual=300)
    insight = completion_insights_tool(ctx)[0]
    assert (insight["completed"], insight["cancelled"]) == (3, 1)
    assert insight["estimate"]["multiplier"] == 2
    assert estimate_duration_tool(ctx, "review", 30)["adjusted_minutes"] == 30
    with pytest.raises(ModelRetry, match="positive"):
        estimate_duration_tool(ctx, "coding", 0)


def test_explicit_memory_tools_are_local_versioned_and_user_scoped(ctx: RunContext[TaskDependencies]) -> None:
    """Facts work without a provider, corrections replace search results and forgetting persists."""
    fact = remember_fact_tool(ctx, " Work Style ", "Morning focus", expires_at=datetime.now(UTC) + timedelta(days=1))
    assert fact["key"] == "work style"
    assert fact["version"] == 1
    assert fact["expires_at"].endswith("Z")
    assert search_facts_tool(ctx, "morning")[0]["value"] == "Morning focus"
    corrected = update_fact_tool(ctx, "work style", "Evening focus")
    assert corrected["version"] == 2
    assert search_facts_tool(ctx, "morning") == []
    assert list_facts_tool(ctx)[0]["value"] == "Evening focus"
    original_memory = ctx.deps.memory
    ctx.deps.memory = MemoryService(ctx.deps.task_repo.db_path, user_id="someone-else")
    assert list_facts_tool(ctx) == []
    ctx.deps.memory = original_memory
    remember_fact_tool(ctx, "old", "Expired", expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert [item["key"] for item in list_facts_tool(ctx)] == ["work style"]
    assert forget_fact_tool(ctx, "work style")["forgotten"] is True
    assert forget_fact_tool(ctx, "work style")["forgotten"] is False
    assert search_facts_tool(ctx, "focus") == []
    with pytest.raises(ModelRetry, match="category"):
        remember_fact_tool(ctx, "invalid", "No mutation", category="unsupported")
    with pytest.raises(ModelRetry, match="timezone"):
        remember_fact_tool(ctx, "invalid", "No mutation", expires_at=datetime(2025, 1, 1))
    with pytest.raises(ModelRetry, match="empty"):
        search_facts_tool(ctx, " ")
    assert list_facts_tool(ctx) == []


def test_invalid_creation_and_dependency_requests_leave_work_unchanged(ctx: RunContext[TaskDependencies]) -> None:
    """Input retries do not create partial work or alter valid edges."""
    with pytest.raises(ModelRetry, match="urgency"):
        create_task_tool(ctx, "Invalid score", 30, 50, "Done", urgency=6)
    with pytest.raises(ModelRetry, match="Goal not found"):
        create_task_tool(ctx, "Invalid goal", 30, 50, "Done", goal_id=uuid4())
    assert ctx.deps.task_repo.list_tasks() == []
    first = create_task_tool(ctx, "First", 30, 50, "Done")
    second = create_task_tool(ctx, "Second", 30, 50, "Done")
    first_id, second_id = UUID(first["task_id"]), UUID(second["task_id"])
    add_dependency_tool(ctx, second_id, first_id)
    with pytest.raises(ModelRetry):
        add_dependency_tool(ctx, first_id, second_id)
    with pytest.raises(ModelRetry):
        add_dependency_tool(ctx, second_id, first_id)
    assert [task.task_id for task in get_blockers_tool(ctx, second_id)] == [first_id]
    assert get_blockers_tool(ctx, first_id) == []
    with pytest.raises(ModelRetry):
        remove_dependency_tool(ctx, first_id, second_id)
    assert [task.task_id for task in get_blockers_tool(ctx, second_id)] == [first_id]


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": -1}, {"offset": -1}, {"status": "unknown"}])
def test_invalid_task_page_inputs_are_correctable(ctx: RunContext[TaskDependencies], kwargs: dict) -> None:
    with pytest.raises(ModelRetry):
        list_tasks_tool(ctx, **kwargs)
