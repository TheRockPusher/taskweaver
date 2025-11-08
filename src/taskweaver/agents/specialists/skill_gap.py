"""SkillGapAnalyzerAgent - Analyzes skill requirements vs. capabilities."""

import logging
from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent.base_agent import BaseSpecialistAgent
from taskweaver.agents.tools import list_tasks_tool

logger = logging.getLogger(__name__)


class SkillGapAnalyzerAgent(BaseSpecialistAgent):
    """Specialist agent for analyzing skill gaps.

    Optimized for:
    - Skill requirement analysis
    - Gap identification (missing vs. insufficient skills)
    - Impact-based prioritization
    - Skill development recommendations
    """

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        """Initialize SkillGapAnalyzerAgent."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "specialists" / "skill_gap.md"
        super().__init__(model=model, system_prompt_path=prompt_path)

        self._agent: Agent[TaskDependencies, str] = Agent(
            model=self.model,
            deps_type=TaskDependencies,
            result_type=str,
            tools=[list_tasks_tool],
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
        return "SkillGapAnalyzerAgent"

    @property
    def description(self) -> str:
        return "Analyzes skill requirements vs. current capabilities and recommends development priorities"

    @property
    def capabilities(self) -> list[str]:
        return [
            "skill_gap_analysis",
            "requirement_analysis",
            "capability_assessment",
            "development_prioritization",
        ]

    def can_handle(self, request: str, context: dict[str, Any] | None = None) -> float:
        """Check if this agent can handle the request."""
        keywords = [
            "skill gap",
            "skills needed",
            "requirements",
            "capabilities",
            "missing skills",
        ]

        if any(phrase in request.lower() for phrase in ["skill gap", "what skills do i need", "missing skills"]):
            return 0.9

        return self._keyword_match_score(request, keywords)

    def _execute(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute skill gap analysis."""
        logger.info(f"[{self.name}] Analyzing skill gaps for: {prompt[:100]}...")

        try:
            result = self._agent.run_sync(prompt, deps=deps)

            return {
                "message": result.data,
                "skill_gap_analyzed": True,
            }

        except Exception as e:
            logger.error(f"[{self.name}] Execution error: {e}", exc_info=True)
            raise
