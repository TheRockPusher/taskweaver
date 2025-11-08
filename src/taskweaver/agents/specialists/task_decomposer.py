"""TaskDecomposerAgent - Breaks down complex goals into actionable tasks."""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent.base_agent import BaseSpecialistAgent
from taskweaver.agents.tools import (
    add_dependency_tool,
    create_task_tool,
)

logger = logging.getLogger(__name__)


class TaskDecomposerAgent(BaseSpecialistAgent):
    """Specialist agent for breaking down complex goals into actionable tasks.

    Optimized for:
    - SMART task creation (Specific, Measurable, Achievable, Relevant, Time-bound)
    - Atomic task decomposition (1-120 minute tasks)
    - Clear dependency identification
    - Measurable requirements
    """

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        """Initialize TaskDecomposerAgent.

        Args:
            model: PydanticAI model identifier
        """
        # Load specialized system prompt
        prompt_path = Path(__file__).parent.parent / "prompts" / "specialists" / "task_decomposer.md"
        super().__init__(model=model, system_prompt_path=prompt_path)

        # Create PydanticAI agent with tools
        self._agent: Agent[TaskDependencies, str] = Agent(
            model=self.model,
            deps_type=TaskDependencies,
            result_type=str,
            tools=[create_task_tool, add_dependency_tool],
        )

        # Add system prompt if loaded
        if self._system_prompt:

            @self._agent.system_prompt
            def get_prompt(ctx) -> str:
                return self._system_prompt

    @property
    def name(self) -> str:
        """Agent name."""
        return "TaskDecomposerAgent"

    @property
    def description(self) -> str:
        """Agent description."""
        return "Breaks down complex goals into actionable, atomic tasks with clear requirements"

    @property
    def capabilities(self) -> list[str]:
        """Agent capabilities."""
        return [
            "task_decomposition",
            "goal_breakdown",
            "task_creation",
            "requirement_definition",
        ]

    def can_handle(self, request: str, context: dict[str, Any] | None = None) -> float:
        """Check if this agent can handle the request.

        Args:
            request: User request
            context: Optional context

        Returns:
            Confidence score (0-1)
        """
        keywords = [
            "create",
            "add",
            "break down",
            "decompose",
            "tasks for",
            "split",
            "divide",
            "plan",
            "organize",
        ]

        # Higher weight for explicit task creation requests
        if any(phrase in request.lower() for phrase in ["create task", "add task", "new task"]):
            return 0.9

        # Medium weight for decomposition language
        if any(word in request.lower() for word in ["break down", "decompose", "split into"]):
            return 0.8

        # Use keyword matching for general case
        return self._keyword_match_score(request, keywords)

    def _execute(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute task decomposition.

        Args:
            prompt: User goal or request
            deps: Task dependencies
            context: Shared context

        Returns:
            Dictionary with tasks_created count and summary
        """
        logger.info(f"[{self.name}] Decomposing goal: {prompt[:100]}...")

        try:
            # Run PydanticAI agent with tools
            result = self._agent.run_sync(prompt, deps=deps)

            # Parse result to extract created tasks
            tasks_created = self._extract_task_count(result.data)

            return {
                "message": result.data,
                "tasks_created": tasks_created,
                "tools_used": [call.tool_name for call in result.all_messages() if hasattr(call, "tool_name")],
            }

        except ValidationError as e:
            logger.error(f"[{self.name}] Validation error: {e}")
            raise ModelRetry(f"Invalid task data: {e}") from e

        except Exception as e:
            logger.error(f"[{self.name}] Execution error: {e}", exc_info=True)
            raise

    def _extract_task_count(self, response: str) -> int:
        """Extract number of tasks created from response.

        Args:
            response: Agent response

        Returns:
            Number of tasks created
        """
        # Look for common patterns in response
        response_lower = response.lower()

        if "created" in response_lower:
            # Try to extract number from "Created N tasks"
            import re

            matches = re.findall(r"created (\d+) task", response_lower)
            if matches:
                return int(matches[0])

        # Default to 0 if can't determine
        return 0
