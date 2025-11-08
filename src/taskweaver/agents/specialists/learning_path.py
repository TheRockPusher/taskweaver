"""LearningPathAgent - Identifies Just-In-Time learning opportunities."""

import logging
from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent.base_agent import BaseSpecialistAgent

logger = logging.getLogger(__name__)


class LearningPathAgent(BaseSpecialistAgent):
    """Specialist agent for identifying JIT (Just-In-Time) learning opportunities.

    Optimized for:
    - JIT learning philosophy (learning derives value from what it unblocks)
    - Skill gap analysis
    - Learning task generation
    - Prerequisite chain reasoning
    """

    def __init__(self, model: str = "openai:gpt-4o"):
        """Initialize LearningPathAgent."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "specialists" / "learning_path.md"
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

                # Inject memories (skill information)
                if ctx.deps.memories:
                    prompt += f"\n\n## User Skills & Context\n\n{ctx.deps.memories}\n"

                return prompt

    @property
    def name(self) -> str:
        return "LearningPathAgent"

    @property
    def description(self) -> str:
        return "Identifies Just-In-Time learning opportunities that unblock high-value tasks"

    @property
    def capabilities(self) -> list[str]:
        return [
            "learning_path",
            "skill_analysis",
            "jit_learning",
            "prerequisite_identification",
        ]

    def can_handle(self, request: str, context: dict[str, Any] | None = None) -> float:
        """Check if this agent can handle the request."""
        keywords = [
            "learn",
            "learning",
            "skill",
            "course",
            "tutorial",
            "study",
            "prerequisite",
        ]

        if any(phrase in request.lower() for phrase in ["what should i learn", "learning path", "skill gap"]):
            return 0.9

        return self._keyword_match_score(request, keywords)

    def _execute(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute learning path identification."""
        logger.info(f"[{self.name}] Identifying learning path for: {prompt[:100]}...")

        try:
            result = self._agent.run_sync(prompt, deps=deps)

            return {
                "message": result.data,
                "learning_path_identified": True,
            }

        except Exception as e:
            logger.error(f"[{self.name}] Execution error: {e}", exc_info=True)
            raise
