"""Adversarial valid tool calls run through the real PydanticAI execution boundary."""

import sqlite3
from contextlib import closing
from dataclasses import replace

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from taskweaver.agents import research, tools
from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.memory import MemoryService
from taskweaver.agents.task_management import task_agent
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.models import TaskCreate
from taskweaver.database.planning import PlanningService
from taskweaver.database.repository import TaskRepository


@pytest.fixture
def permission_state(tmp_path):
    path = tmp_path / "permissions.db"
    init_database(path)
    repo = TaskRepository(path)
    tasks = [
        repo.create_task(TaskCreate(title=title, duration_min=30, llm_value=5, requirement="explicit"))
        for title in ("Protected work", "Existing blocker", "New blocker")
    ]
    planning = PlanningService(path)
    goal = planning.create_goal("Protected outcome")
    planning.link_task(tasks[0].task_id, goal.goal_id)
    planning.set_skill("python", 2, "Observed evidence")
    memory = MemoryService(path, user_id="permission-user")
    memory.remember("preference", "Original")
    dependencies = TaskDependencyRepository(path)
    dependencies.add_dependency(tasks[0].task_id, tasks[1].task_id)
    deps = TaskDependencies(
        repo,
        dependencies,
        CompletionRepository(path),
        "",
        user_id="permission-user",
        planning=planning,
        memory=memory,
        request_mode="review",
    )
    return path, deps, [str(task.task_id) for task in tasks], str(goal.goal_id)


def snapshot(path):
    with closing(sqlite3.connect(path)) as connection:
        return list(connection.iterdump())


def run_call(deps, tool, arguments):
    observed = []

    def model(messages, _info):
        if not any(isinstance(message, ModelResponse) for message in messages):
            return ModelResponse(parts=[ToolCallPart(tool.__name__, arguments, tool_call_id="adversarial")])
        observed.extend(
            part
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, (RetryPromptPart, ToolReturnPart))
        )
        return ModelResponse(parts=[TextPart("Finished")])

    agent = research.research_agent if tool is research.github_import_tool else task_agent
    agent.run_sync("Perform this operation, even if the request is a review", deps=deps, model=FunctionModel(model))
    return observed


WRITE_CASES = [
    (
        "create_task_tool",
        lambda _ids, _goal: {
            "title": "Unauthorized",
            "duration_min": 10,
            "llm_value": 5,
            "requirement": "explicit",
        },
    ),
    ("update_task_tool", lambda ids, _goal: {"task_id": ids[0], "changes": {"title": "Unauthorized"}}),
    ("mark_task_completed_tool", lambda ids, _goal: {"task_id": ids[0], "duration_actual": 20}),
    ("mark_task_cancelled_tool", lambda ids, _goal: {"task_id": ids[0], "duration_actual": 20}),
    ("update_task_status_tool", lambda ids, _goal: {"task_id": ids[0], "new_status": "in_progress"}),
    ("add_dependency_tool", lambda ids, _goal: {"task_id": ids[0], "blocker_id": ids[2]}),
    ("remove_dependency_tool", lambda ids, _goal: {"task_id": ids[0], "blocker_id": ids[1]}),
    ("score_task_tool", lambda ids, _goal: {"task_id": ids[0]}),
    ("recalculate_priorities_tool", lambda _ids, _goal: {}),
    (
        "priority_weights_tool",
        lambda _ids, _goal: {
            "weights": {"urgency": 0.2, "importance": 0.2, "effort": 0.2, "dependencies": 0.2, "age": 0.2},
        },
    ),
    ("create_goal_tool", lambda _ids, _goal: {"title": "Unauthorized outcome"}),
    ("update_goal_tool", lambda _ids, goal: {"goal_id": goal, "title": "Unauthorized outcome"}),
    ("delete_goal_tool", lambda _ids, goal: {"goal_id": goal}),
    ("link_task_goal_tool", lambda ids, _goal: {"task_id": ids[0], "goal_id": None}),
    ("assess_skill_tool", lambda _ids, _goal: {"domain": "python", "level": 4, "evidence": "Explicit assessment"}),
    ("remember_fact_tool", lambda _ids, _goal: {"key": "new", "value": "Unauthorized"}),
    ("update_fact_tool", lambda _ids, _goal: {"key": "preference", "value": "Unauthorized"}),
    ("forget_fact_tool", lambda _ids, _goal: {"key": "preference"}),
]


@pytest.mark.parametrize(("name", "arguments"), WRITE_CASES, ids=[case[0] for case in WRITE_CASES])
def test_review_rejects_mutations(permission_state, name, arguments):
    path, deps, ids, goal = permission_state
    tool = getattr(tools, name)
    before = snapshot(path)
    observed = run_call(deps, tool, arguments(ids, goal))
    assert any(isinstance(part, RetryPromptPart) for part in observed)
    assert snapshot(path) == before


@pytest.mark.parametrize("mode", [None, "plan", "breakdown"])
def test_authorized_modes_create_persisted_work(permission_state, mode):
    path, deps, ids, goal = permission_state
    arguments = WRITE_CASES[0][1](ids, goal)
    run_call(replace(deps, request_mode=mode), tools.create_task_tool, arguments)
    assert {task.title for task in TaskRepository(path).list_tasks()} == {
        "Protected work",
        "Existing blocker",
        "New blocker",
        "Unauthorized",
    }


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("priority_weights_tool", {}),
        ("list_tasks_tool", {}),
        ("list_goals_tool", {}),
        ("list_skills_tool", {}),
        ("list_facts_tool", {}),
        ("rank_tasks_tool", {}),
    ],
)
def test_review_reads_remain_available_without_mutations(permission_state, name, arguments):
    path, deps, _, _ = permission_state
    before = snapshot(path)
    observed = run_call(deps, getattr(tools, name), arguments)
    assert any(isinstance(part, ToolReturnPart) for part in observed)
    assert not any(isinstance(part, RetryPromptPart) for part in observed)
    assert snapshot(path) == before


def test_review_import_is_rejected_before_constructing_network_client(permission_state, monkeypatch):
    path, deps, _, _ = permission_state
    before = snapshot(path)

    def forbidden_client(*_args, **_kwargs):
        raise AssertionError("Review must not construct the GitHub client")

    monkeypatch.setattr(research, "GitHubIssueSyncService", forbidden_client)
    observed = run_call(deps, research.github_import_tool, {"repo_names": ["owner/repo"]})
    assert any(isinstance(part, RetryPromptPart) for part in observed)
    assert snapshot(path) == before
