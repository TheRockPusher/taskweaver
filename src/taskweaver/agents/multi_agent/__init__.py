"""Multi-agent framework for TaskWeaver.

This package provides a coordinated multi-agent system where specialist agents
handle different aspects of task management:

- TaskDecomposerAgent: Breaks down complex goals into actionable tasks
- DependencyAnalyzerAgent: Analyzes and validates task dependencies
- EstimationAgent: Predicts task durations based on historical patterns
- PriorityCalculatorAgent: Calculates task priorities using multi-factor scoring
- LearningPathAgent: Identifies Just-In-Time learning opportunities
- SkillGapAnalyzerAgent: Analyzes skill requirements vs capabilities

The coordinator routes requests to appropriate specialists and aggregates results.
"""

from taskweaver.agents.multi_agent.coordinator import MultiAgentCoordinator
from taskweaver.agents.multi_agent.message import AgentMessage, MessageType
from taskweaver.agents.multi_agent.protocol import AgentResult, SpecialistAgent
from taskweaver.agents.multi_agent.registry import AgentRegistry

__all__ = [
    "MultiAgentCoordinator",
    "AgentRegistry",
    "SpecialistAgent",
    "AgentResult",
    "AgentMessage",
    "MessageType",
]
