"""PriorityCalculatorAgent - Calculates task priorities using multi-factor scoring."""

import logging
from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent.base_agent import BaseSpecialistAgent
from taskweaver.agents.tools import get_blocked_tool, get_task_details_tool, list_tasks_tool

logger = logging.getLogger(__name__)


class PriorityCalculatorAgent(BaseSpecialistAgent):
    """Specialist agent for calculating task priorities.

    Optimized for:
    - Multi-factor priority scoring
    - DAG-aware priority inheritance
    - Value vs. effort analysis
    - Urgency multipliers (deadlines, blockers)
    """

    def __init__(self, model: str = "openai:gpt-4o-mini", config: dict[str, float] | None = None):
        """Initialize PriorityCalculatorAgent.

        Args:
            model: PydanticAI model identifier
            config: Priority algorithm configuration (weights, etc.)
        """
        prompt_path = Path(__file__).parent.parent / "prompts" / "specialists" / "priority_calculator.md"
        super().__init__(model=model, system_prompt_path=prompt_path)

        # Priority algorithm configuration
        self.config = config or {
            "weight_value": 0.6,
            "weight_effort": 0.3,
            "weight_blockers": 0.1,
        }

        self._agent: Agent[TaskDependencies, str] = Agent(
            model=self.model,
            deps_type=TaskDependencies,
            result_type=str,
            tools=[list_tasks_tool, get_task_details_tool, get_blocked_tool],
        )

        if self._system_prompt:

            @self._agent.system_prompt
            def get_prompt(ctx) -> str:
                prompt = self._system_prompt

                # Inject priority config
                config_section = "\n## Priority Algorithm Configuration\n\n"
                for key, value in self.config.items():
                    config_section += f"- {key}: {value}\n"

                return prompt + "\n" + config_section

    @property
    def name(self) -> str:
        return "PriorityCalculatorAgent"

    @property
    def description(self) -> str:
        return "Calculates task priorities using multi-factor scoring (value, effort, urgency)"

    @property
    def capabilities(self) -> list[str]:
        return [
            "priority_calculation",
            "value_analysis",
            "effort_estimation",
            "urgency_scoring",
            "ranking",
        ]

    def can_handle(self, request: str, context: dict[str, Any] | None = None) -> float:
        """Check if this agent can handle the request."""
        keywords = [
            "priority",
            "prioritize",
            "important",
            "urgent",
            "rank",
            "sort",
            "order by",
        ]

        if any(phrase in request.lower() for phrase in ["calculate priority", "prioritize tasks", "rank tasks"]):
            return 0.9

        return self._keyword_match_score(request, keywords)

    def _execute(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute priority calculation."""
        logger.info(f"[{self.name}] Calculating priorities for: {prompt[:100]}...")

        try:
            result = self._agent.run_sync(prompt, deps=deps)

            return {
                "message": result.data,
                "priority_calculated": True,
            }

        except Exception as e:
            logger.error(f"[{self.name}] Execution error: {e}", exc_info=True)
            raise
