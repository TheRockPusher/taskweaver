# TaskWeaver Multi-Agent System - User Guide

## Overview

TaskWeaver's multi-agent architecture is a coordinated system of specialist agents, each optimized for specific task management domains. Instead of a single general-purpose agent handling all requests, specialist agents provide deeper expertise in their respective areas.

## Why Multi-Agent?

**Traditional Single Agent**:
- One agent handles all requests
- General-purpose prompts
- Sequential processing
- No specialized reasoning

**Multi-Agent System**:
- ✅ **Specialized Expertise**: Each agent has domain-specific prompts and reasoning
- ✅ **Parallel Execution**: Independent agents run concurrently
- ✅ **Better Quality**: Specialized prompts produce higher-quality results
- ✅ **Scalable**: Add new specialists without changing core system
- ✅ **Intelligent Routing**: Requests automatically routed to best agent

## Specialist Agents

### 1. TaskDecomposerAgent 🔨
**Purpose**: Break down complex goals into actionable tasks

**Best for**:
- "Create tasks for building a REST API"
- "Break down my app development project"
- "Add tasks for implementing authentication"

**Optimizations**:
- SMART task creation (Specific, Measurable, Achievable, Relevant, Time-bound)
- Atomic decomposition (1-120 minute tasks)
- Clear measurable requirements
- Automatic dependency identification

**Model**: `gpt-4o-mini` (fast, cost-effective)

---

### 2. DependencyAnalyzerAgent 🔗
**Purpose**: Analyze task dependencies and relationships

**Best for**:
- "Check if my dependencies have any cycles"
- "What's the critical path for my project?"
- "Find tasks that are blocking the most work"

**Optimizations**:
- DAG (Directed Acyclic Graph) reasoning
- Cycle detection algorithms
- Critical path identification
- Redundant dependency removal

**Model**: `gpt-4o` (stronger reasoning for graph problems)

---

### 3. EstimationAgent ⏱️
**Purpose**: Estimate task durations based on historical patterns

**Best for**:
- "How long will it take to implement OAuth?"
- "Estimate duration for these tasks"
- "What's a realistic timeline for this project?"

**Optimizations**:
- Pattern recognition from completion history
- Variance analysis (tracks estimation accuracy)
- Confidence scoring
- Complexity adjustments

**Model**: `gpt-4o-mini`

---

### 4. PriorityCalculatorAgent 🎯
**Purpose**: Calculate task priorities using multi-factor scoring

**Best for**:
- "What should I work on next?"
- "Prioritize my tasks"
- "Rank my backlog by importance"

**Optimizations**:
- Multi-factor algorithm (value, effort, urgency, risk, alignment)
- DAG-aware (considers downstream impact)
- Deadline detection
- Blocker multipliers

**Model**: `gpt-4o-mini`

**Priority Formula**:
```
Priority = Urgency_Multiplier × Value / (1 + Effort_Cost)
```

---

### 5. LearningPathAgent 📚
**Purpose**: Identify Just-In-Time (JIT) learning opportunities

**Best for**:
- "What should I learn to unblock my work?"
- "Identify my skill gaps"
- "Recommend a learning path"

**Optimizations**:
- JIT learning philosophy (learn exactly what you need, when you need it)
- ROI calculation (value unlocked per hour of learning)
- Prerequisite chain analysis
- Timing recommendations

**Model**: `gpt-4o` (strategic reasoning)

---

### 6. SkillGapAnalyzerAgent 🎓
**Purpose**: Analyze skill requirements vs. current capabilities

**Best for**:
- "What skills do I need for my upcoming work?"
- "Analyze my skill gaps"
- "Prioritize skill development"

**Optimizations**:
- Requirement extraction from tasks
- Gap classification (critical, high, moderate, low)
- Impact-based prioritization
- Over-investment warnings

**Model**: `gpt-4o-mini`

---

## Getting Started

### 1. Enable Multi-Agent System

Copy the example configuration:
```bash
cp config.toml.multi-agent-example config.toml
```

Edit `config.toml`:
```toml
# Enable multi-agent system
multi_agent_enabled = true
```

### 2. Configure Agents

**Quick Start** (use defaults):
```toml
# All agents enabled with sensible defaults
multi_agent_enabled = true
```

**Custom Configuration**:
```toml
# Enable specific agents
agent_task_decomposer_enabled = true
agent_dependency_analyzer_enabled = true
agent_estimation_enabled = false  # Disable estimation agent

# Use different models per agent
agent_task_decomposer_model = "gpt-4o-mini"  # Fast & cheap
agent_dependency_analyzer_model = "gpt-4o"   # Powerful reasoning
```

### 3. Run TaskWeaver

```bash
# CLI mode
taskweaver chat

# TUI mode
taskweaver tui
```

The multi-agent system runs transparently! Requests are automatically routed to the best specialist.

---

## How It Works

### Request Routing

The **MultiAgentCoordinator** analyzes your request and routes it to the best specialist:

```
User: "Create tasks for building a mobile app"
         ↓
   Coordinator analyzes intent
         ↓
   Routes to TaskDecomposerAgent
         ↓
   Agent decomposes goal into tasks
         ↓
   Result returned to user
```

### Workflow Orchestration

For complex requests, multiple agents work sequentially:

```
User: "Create and prioritize tasks for authentication"
         ↓
   TaskDecomposerAgent (creates tasks)
         ↓
   PriorityCalculatorAgent (calculates priorities)
         ↓
   Combined result returned
```

### Parallel Execution

Independent agents can run concurrently:

```
User request triggers multiple agents
         ↓
    ┌────┴────┐
    │         │
Agent 1    Agent 2  (run in parallel)
    │         │
    └────┬────┘
         ↓
    Results aggregated
```

---

## Configuration Reference

### Core Settings

```toml
# Enable/disable multi-agent system
multi_agent_enabled = true

# Allow parallel execution (faster)
multi_agent_parallel = true

# Max concurrent agents
multi_agent_max_parallel = 3

# Fall back to general agent if specialist fails
multi_agent_fallback = true

# Minimum confidence to route to specialist (0.0-1.0)
# Lower = more aggressive, Higher = more conservative
multi_agent_min_confidence = 0.3
```

### Per-Agent Settings

Each agent can be individually enabled/disabled and use different models:

```toml
agent_task_decomposer_enabled = true
agent_task_decomposer_model = "gpt-4o-mini"

agent_dependency_analyzer_enabled = true
agent_dependency_analyzer_model = "gpt-4o"

agent_estimation_enabled = true
agent_estimation_model = "gpt-4o-mini"

agent_priority_calculator_enabled = true
agent_priority_calculator_model = "gpt-4o-mini"

agent_learning_path_enabled = true
agent_learning_path_model = "gpt-4o"

agent_skill_gap_enabled = true
agent_skill_gap_model = "gpt-4o-mini"
```

---

## Performance Tuning

### For Speed
```toml
# Use fast model everywhere
agent_task_decomposer_model = "gpt-4o-mini"
agent_dependency_analyzer_model = "gpt-4o-mini"
agent_estimation_model = "gpt-4o-mini"
agent_priority_calculator_model = "gpt-4o-mini"
agent_learning_path_model = "gpt-4o-mini"
agent_skill_gap_model = "gpt-4o-mini"

# Max parallelization
multi_agent_parallel = true
multi_agent_max_parallel = 5
```

### For Quality
```toml
# Use powerful models for complex reasoning
agent_dependency_analyzer_model = "gpt-4o"  # Graph reasoning
agent_learning_path_model = "gpt-4o"        # Strategic analysis

# Use fast models for simple tasks
agent_task_decomposer_model = "gpt-4o-mini"
agent_estimation_model = "gpt-4o-mini"
agent_priority_calculator_model = "gpt-4o-mini"
agent_skill_gap_model = "gpt-4o-mini"
```

### For Cost
```toml
# Disable unused agents
agent_estimation_enabled = false
agent_learning_path_enabled = false
agent_skill_gap_enabled = false

# Use cheapest models
agent_task_decomposer_model = "gpt-4o-mini"
agent_dependency_analyzer_model = "gpt-4o-mini"
agent_priority_calculator_model = "gpt-4o-mini"

# Higher confidence threshold (route less often)
multi_agent_min_confidence = 0.5
```

---

## Examples

### Example 1: Task Decomposition

**Input**:
```
"Create tasks for building a REST API with authentication"
```

**Routed to**: TaskDecomposerAgent

**Output**:
```
Created 6 tasks for "REST API with authentication":

1. Design API endpoints (30 min) - OpenAPI spec with all auth endpoints
2. Implement user registration (45 min) - POST /register creates user in DB
3. Implement JWT generation (60 min) - Function returns valid signed JWT
4. Implement login endpoint (45 min) - POST /login returns JWT for valid credentials [Depends on: JWT generation]
5. Add refresh token logic (30 min) - POST /refresh returns new JWT [Depends on: JWT generation]
6. Write API integration tests (60 min) - Tests cover all endpoints >80% coverage [Depends on: all above]

Total estimated time: 270 minutes (~4.5 hours)
```

---

### Example 2: Dependency Analysis

**Input**:
```
"Check if my task dependencies have any problems"
```

**Routed to**: DependencyAnalyzerAgent

**Output**:
```
## Dependency Analysis

**Graph Status**: Contains redundant edges

**Findings**:
- Found 2 redundant dependencies (transitive paths exist)
- No cycles detected ✓
- Critical path identified: 5 tasks, 180 minutes

**Redundant Dependencies**:
- Task C → Task A (already via C → B → A)
- Task E → Task B (already via E → D → C → B)

**Critical Path**: A → B → C → D → E (180 minutes)

**Recommendations**:
1. Remove redundant dependency: Task C → Task A
2. Remove redundant dependency: Task E → Task B
3. Consider parallelizing Tasks F and G (no dependencies between them)
```

---

### Example 3: Learning Path Identification

**Input**:
```
"What should I learn to unblock my upcoming work?"
```

**Routed to**: LearningPathAgent

**Output**:
```
## Just-In-Time Learning Recommendation

**Skill**: TypeScript (Level 3 required)
**Current Level**: Level 1
**Gap**: Insufficient

**Value Unlock**:
- Migrate auth service to TypeScript (Priority: 42)
- Add type safety to API layer (Priority: 38)
- Set up TypeScript build pipeline (Priority: 29)
- Total: 109 priority points

**Learning Time**: 90 minutes
**ROI**: 1.21 priority points per minute (very high!)

**Recommended Resource**: "TypeScript Essentials for JavaScript Developers"

**Timing**: NOW - complete before starting TypeScript migration tasks

**Why This Matters**:
This 90-minute investment unlocks 6 hours of high-priority work.
All three blocked tasks are on your critical path.
```

---

## Troubleshooting

### Multi-Agent Not Working

**Check configuration**:
```bash
# View current config
cat config.toml

# Verify multi_agent_enabled = true
```

**Check logs**:
```bash
# Enable debug logging
export LOGURU_LEVEL=DEBUG
taskweaver chat
```

### Agent Not Triggering

**Lower confidence threshold**:
```toml
# More aggressive routing
multi_agent_min_confidence = 0.2  # Default: 0.3
```

**Check agent is enabled**:
```toml
agent_task_decomposer_enabled = true  # Make sure not false
```

### Agent Errors

**Check API keys**:
```bash
# Verify .env file has correct keys
cat .env

# For OpenAI
OPENAI_API_KEY=sk-...

# For Anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

**Check model availability**:
```toml
# Ensure model name is correct
agent_task_decomposer_model = "gpt-4o-mini"  # Not "gpt4omini"
```

---

## Advanced Usage

### Force Specific Agent

```python
from taskweaver.agents.multi_agent_setup import create_multi_agent_system
from taskweaver.config import get_config

config = get_config()
coordinator = create_multi_agent_system(config)

# Force specific agent
result = coordinator.process(
    "Analyze dependencies",
    deps=task_deps,
    force_agent="DependencyAnalyzerAgent"
)
```

### Get System Stats

```python
stats = coordinator.get_stats()
print(f"Enabled agents: {stats['enabled_agents']}")
print(f"Capabilities: {stats['capabilities']}")
```

### Async Execution

```python
# Run agents in parallel
result = await coordinator.process_async(
    "Create and prioritize tasks",
    deps=task_deps,
    parallel=True
)
```

---

## Best Practices

### 1. Start Simple
- Enable multi-agent system
- Use default settings
- See how it performs

### 2. Tune Gradually
- Adjust confidence threshold based on results
- Disable unused agents
- Try different models per agent

### 3. Monitor Performance
- Check execution times (in debug logs)
- Compare single-agent vs multi-agent quality
- Adjust based on your needs

### 4. Cost Management
- Use `gpt-4o-mini` for most agents
- Only use `gpt-4o` for complex reasoning (DependencyAnalyzer, LearningPath)
- Set higher confidence thresholds to route less often

---

## FAQ

**Q: Does multi-agent slow down responses?**
A: No! With parallel execution enabled, multiple agents can run faster than a single agent handling complex requests.

**Q: Can I use different models for different agents?**
A: Yes! Each agent has its own model configuration.

**Q: What happens if a specialist fails?**
A: If `multi_agent_fallback = true`, the system falls back to the general-purpose agent.

**Q: Can I add custom agents?**
A: Yes! Implement the `SpecialistAgent` protocol and register with the registry. See the architecture documentation for details.

**Q: Does this work with local models?**
A: Yes! Any PydanticAI-supported model works. Set the model name and API endpoint appropriately.

**Q: How much does this cost?**
A: Cost depends on models used. With all `gpt-4o-mini` agents, cost is similar to the single-agent system. Using `gpt-4o` for some agents increases cost proportionally.

---

## What's Next?

- **Try it**: Enable multi-agent and see the difference!
- **Experiment**: Try different configurations
- **Provide Feedback**: Let us know which agents are most useful
- **Contribute**: Add new specialist agents for specific domains

For detailed architecture information, see [MULTI_AGENT_ARCHITECTURE.md](./MULTI_AGENT_ARCHITECTURE.md).
