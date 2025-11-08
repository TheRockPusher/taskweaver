"""EstimationAgent - Estimates task durations based on historical patterns."""

import logging
from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent.base_agent import BaseSpecialistAgent

logger = logging.getLogger(__name__)


class EstimationAgent(BaseSpecialistAgent):
    """Specialist agent for estimating task durations.

    Optimized for:
    - Historical pattern analysis
    - Variance-adjusted estimation
    - Confidence scoring
    - Complexity-based adjustments
    """

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        """Initialize EstimationAgent."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "specialists" / "estimation.md"
        super().__init__(model=model, system_prompt_path=prompt_path)

        self._agent: Agent[TaskDependencies, str] = Agent(
            model=self.model,
            deps_type=TaskDependencies,
            result_type=str,
        )

        if self._system_prompt:

            @self._agent.system_prompt
            def get_prompt(ctx) -> str:
                prompt = self._system_prompt

                # Inject completion history if available
                if ctx.deps.completion_repo:
                    try:
                        completions = ctx.deps.completion_repo.list_completions(limit=20)
                        if completions:
                            history = "\n## Recent Completion History\n\n"
                            for comp in completions[:10]:
                                variance = ((comp.duration_actual - comp.duration_expected) / comp.duration_expected) * 100
                                history += f"- Task: {comp.task_id}, Expected: {comp.duration_expected}min, Actual: {comp.duration_actual}min, Variance: {variance:+.1f}%\n"
                            prompt += "\n" + history
                    except Exception as e:
                        logger.warning(f"Could not load completion history: {e}")

                return prompt

    @property
    def name(self) -> str:
        return "EstimationAgent"

    @property
    def description(self) -> str:
        return "Estimates task durations based on historical patterns and complexity analysis"

    @property
    def capabilities(self) -> list[str]:
        return [
            "duration_estimation",
            "pattern_analysis",
            "variance_prediction",
            "confidence_scoring",
        ]

    def can_handle(self, request: str, context: dict[str, Any] | None = None) -> float:
        """Check if this agent can handle the request."""
        keywords = [
            "estimate",
            "how long",
            "duration",
            "time",
            "take to",
            "effort",
        ]

        if any(phrase in request.lower() for phrase in ["how long will", "estimate duration", "estimate time"]):
            return 0.9

        return self._keyword_match_score(request, keywords)

    def _execute(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute estimation."""
        logger.info(f"[{self.name}] Estimating duration for: {prompt[:100]}...")

        try:
            result = self._agent.run_sync(prompt, deps=deps)

            return {
                "message": result.data,
                "estimation_complete": True,
            }

        except Exception as e:
            logger.error(f"[{self.name}] Execution error: {e}", exc_info=True)
            raise
