"""Specialist agents for TaskWeaver multi-agent system.

Each specialist focuses on a specific domain:
- TaskDecomposerAgent: Breaks down complex goals into tasks
- DependencyAnalyzerAgent: Analyzes task dependencies
- EstimationAgent: Estimates task durations
- PriorityCalculatorAgent: Calculates task priorities
- LearningPathAgent: Identifies learning opportunities
- SkillGapAnalyzerAgent: Analyzes skill requirements
"""

from taskweaver.agents.specialists.dependency_analyzer import DependencyAnalyzerAgent
from taskweaver.agents.specialists.estimation import EstimationAgent
from taskweaver.agents.specialists.learning_path import LearningPathAgent
from taskweaver.agents.specialists.priority_calculator import PriorityCalculatorAgent
from taskweaver.agents.specialists.skill_gap import SkillGapAnalyzerAgent
from taskweaver.agents.specialists.task_decomposer import TaskDecomposerAgent

__all__ = [
    "TaskDecomposerAgent",
    "DependencyAnalyzerAgent",
    "EstimationAgent",
    "PriorityCalculatorAgent",
    "LearningPathAgent",
    "SkillGapAnalyzerAgent",
]
