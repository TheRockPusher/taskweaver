"""Calculator failures become correctable tool retries through real agent execution."""

from pathlib import Path

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.tools import calculator_tool
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.repository import TaskRepository


@pytest.mark.parametrize("expression", ["10 / 0", "", "2 + * 2", "x + 5", "print(5)", "2 ** 1000000000"])
def test_invalid_calculation_can_be_corrected_without_aborting_agent(db_path: Path, expression: str) -> None:
    deps = TaskDependencies(
        TaskRepository(db_path), TaskDependencyRepository(db_path), CompletionRepository(db_path), ""
    )
    replies = []
    step = 0

    def provider(messages, _info):
        nonlocal step
        step += 1
        if step == 1:
            return ModelResponse(parts=[ToolCallPart("calculator_tool", {"expression": expression})])
        request = messages[-1]
        assert isinstance(request, ModelRequest)
        replies.extend(request.parts)
        if step == 2:
            return ModelResponse(parts=[ToolCallPart("calculator_tool", {"expression": "85.0 / 120"})])
        return ModelResponse(parts=[TextPart("Calculation completed")])

    agent = Agent[TaskDependencies, str](deps_type=TaskDependencies, tools=[calculator_tool])
    agent.run_sync("Calculate priority", deps=deps, model=FunctionModel(provider))
    assert any(isinstance(part, RetryPromptPart) for part in replies)
    assert [part.content for part in replies if isinstance(part, ToolReturnPart)] == ["85.0 / 120 = 0.7083"]
    assert deps.task_repo.list_tasks() == []
