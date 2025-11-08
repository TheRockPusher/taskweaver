# TaskWeaver Multi-Agent Architecture

## Overview

TaskWeaver's multi-agent architecture transforms the single monolithic agent into a coordinated system of specialist agents, each optimized for specific reasoning tasks. This design preserves the existing tool infrastructure while enabling parallel execution, specialized reasoning, and improved scalability.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                      │
│                     (CLI / TUI / API - unchanged)                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Agent Coordinator                       │
│  • Request routing & decomposition                               │
│  • Agent lifecycle management                                    │
│  • Result aggregation & validation                               │
│  • Parallel execution orchestration                              │
│  • Fallback & error recovery                                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Specialist  │  │  Specialist  │  │  Specialist  │
│   Agents     │  │   Agents     │  │   Agents     │
│  (Layer 1)   │  │  (Layer 2)   │  │  (Layer 3)   │
└─────────────┘  └─────────────┘  └─────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Shared Infrastructure                        │
│  • Tool Registry (13 existing tools)                             │
│  • TaskDependencies (repositories + memory)                      │
│  • Mem0 Semantic Memory (shared context)                         │
│  • Langfuse Observability (agent traces)                         │
└─────────────────────────────────────────────────────────────────┘
```

## Design Principles

1. **Separation of Concerns**: Each agent specializes in one domain
2. **Backward Compatibility**: Existing CLI/TUI interfaces unchanged
3. **Tool Reuse**: All agents share the existing 13 tools
4. **Parallel Execution**: Independent agents run concurrently when possible
5. **Graceful Degradation**: Fallback to general-purpose agent on specialist failure
6. **Observable**: Every agent action traced via Langfuse
7. **Composable**: Agents can invoke other agents for complex workflows

## Specialist Agents

### 1. TaskDecomposerAgent
**Purpose**: Break down complex goals into actionable, atomic tasks

**Optimizations**:
- System prompt focused on SMART task creation
- Uses `create_task_tool` and `add_dependency_tool`
- Enforces measurable requirements
- Validates task atomicity (1-120 min duration)

**Input**: High-level goal description
**Output**: List of tasks with dependencies

**Example**:
```
Input: "Build a REST API for user authentication"
Output:
  - Design API endpoints (30 min)
  - Implement JWT token generation (60 min) [depends on: Design API endpoints]
  - Create login endpoint (45 min) [depends on: JWT generation]
  - Add refresh token logic (30 min) [depends on: JWT generation]
  - Write API tests (45 min) [depends on: all above]
```

---

### 2. DependencyAnalyzerAgent
**Purpose**: Reason about task relationships, detect cycles, identify critical paths

**Optimizations**:
- Graph reasoning system prompt (DAG terminology)
- Uses `add_dependency_tool`, `remove_dependency_tool`, `get_blockers_tool`
- Cycle detection heuristics
- Critical path identification

**Input**: Set of tasks
**Output**: Dependency recommendations + validation

**Example**:
```
Input: [Task A, Task B (depends on A), Task C (depends on B), Task D (depends on C, A)]
Output:
  - Critical path: A → B → C → D (longest chain: 4 tasks)
  - Redundant: D depends on A (transitively via B, C)
  - Recommendation: Remove D→A dependency
```

---

### 3. EstimationAgent
**Purpose**: Predict task duration based on historical patterns

**Optimizations**:
- Access to `completion_repo` for pattern learning
- Variance analysis from past estimates
- Confidence scoring
- Domain-specific estimation heuristics

**Input**: Task description + completion history
**Output**: Duration estimate (minutes) + confidence (0-1)

**Algorithm**:
```python
1. Find similar past tasks (semantic similarity via Mem0)
2. Calculate average actual duration
3. Adjust for variance patterns
4. Apply complexity multipliers
5. Return estimate + confidence
```

**Example**:
```
Input: "Implement OAuth2 login endpoint"
Past similar tasks:
  - "Create JWT auth endpoint" → estimated: 60 min, actual: 75 min (+25%)
  - "Build login API" → estimated: 45 min, actual: 50 min (+11%)

Output: 65 minutes (confidence: 0.72)
Reasoning: Average actual 62.5 min, +18% variance pattern, rounded to 65
```

---

### 4. PriorityCalculatorAgent
**Purpose**: Calculate task priority using multi-factor scoring

**Optimizations**:
- Implements sophisticated priority algorithm (value, urgency, dependencies)
- Uses `list_tasks_tool`, `get_blocked_tool` for downstream impact
- DAG-aware priority inheritance
- Configurable weights for different factors

**Input**: Task + dependency graph
**Output**: Priority score + breakdown

**Algorithm** (from spec):
```
P = urgency_multiplier × value / (1 + effort_cost)

Where:
- value = weighted sum of (monetary_value, time_value, alignment, risk, learning_unlock)
- urgency_multiplier = deadline_urgency × blocker_urgency
- effort_cost = duration × (1 + complexity_penalty + uncertainty_penalty)
```

**Example**:
```
Input: Task "Implement CI/CD pipeline"
  - Duration: 120 min
  - LLM value: 85/100
  - Blocks: 3 tasks
  - No deadline

Output: Priority 42.3
  Breakdown:
    - Base value: 85
    - Effort cost: 2.0 hours × 1.15 (complexity) = 2.3
    - Blocker multiplier: 1.3 (blocks 3 tasks)
    - Final: 1.3 × 85 / (1 + 2.3) = 42.3
```

---

### 5. LearningPathAgent
**Purpose**: Identify Just-In-Time (JIT) learning opportunities

**Optimizations**:
- Understands JIT philosophy: learning derives value from what it unblocks
- Skill gap analysis
- Learning task generation
- Prerequisite chain reasoning

**Input**: Task list + current skill levels (via Mem0)
**Output**: Recommended learning tasks + justification

**Example**:
```
Input: Tasks require "Kubernetes" skill (level 3)
      User current skill: Kubernetes (level 1)

Blocked tasks:
  - Deploy app to K8s cluster (priority: 38)
  - Set up ingress controller (priority: 42)
  - Configure auto-scaling (priority: 29)

Output:
  Learning Task: "Complete 'Kubernetes Essentials' course (90 min)"
  Value unlock: 109 priority points across 3 tasks
  Recommendation: High priority - do before deployment tasks
```

---

### 6. SkillGapAnalyzerAgent
**Purpose**: Analyze skill requirements vs. current capabilities

**Optimizations**:
- Cross-references tasks with skill database
- Identifies missing vs. insufficient skills
- Recommends skill acquisition strategy
- Prioritizes skill development by impact

**Input**: Task list + user skill profile
**Output**: Skill gap report + development recommendations

**Example**:
```
Input: Upcoming tasks in backlog
Output:
  Critical gaps (blocking ≥3 tasks):
    - Docker (required: 3, current: 1) → blocks 5 tasks
    - GraphQL (required: 2, current: 0) → blocks 3 tasks

  Nice-to-have (quality improvement):
    - TypeScript (required: 4, current: 3) → improves 2 tasks

  Recommendation:
    1. Learn Docker basics (2 hours) - unblocks 5 tasks
    2. GraphQL tutorial (1 hour) - unblocks 3 tasks
```

---

## Coordinator Behavior

### Request Routing Logic

```python
def route_request(user_input: str, context: TaskDependencies) -> AgentPlan:
    """Route user request to appropriate specialist(s)."""

    # Intent classification
    if "create" in input or "add" in input or "break down" in input:
        return TaskDecomposerAgent

    elif "dependency" in input or "depends on" in input or "blocker" in input:
        return DependencyAnalyzerAgent

    elif "estimate" in input or "how long" in input:
        return EstimationAgent

    elif "priority" in input or "important" in input or "urgent" in input:
        return PriorityCalculatorAgent

    elif "learn" in input or "skill" in input or "course" in input:
        return LearningPathAgent

    elif complex_workflow_detected(input):
        # Multi-agent orchestration
        return [TaskDecomposerAgent, DependencyAnalyzerAgent, PriorityCalculatorAgent]

    else:
        # Fallback to general-purpose agent
        return GeneralPurposeAgent
```

### Parallel Execution

For independent operations:
```python
async def execute_parallel(agents: list[SpecialistAgent], prompt: str):
    results = await asyncio.gather(
        agents[0].run_async(prompt, deps),
        agents[1].run_async(prompt, deps),
        agents[2].run_async(prompt, deps)
    )
    return aggregate_results(results)
```

### Sequential Orchestration

For dependent workflows:
```python
def execute_workflow(workflow: list[AgentStep]):
    context = {}
    for step in workflow:
        result = step.agent.run(step.prompt, deps, context)
        context[step.output_key] = result
    return context
```

**Example Workflow**: "Create tasks for new feature"
```python
Workflow:
1. TaskDecomposerAgent → creates tasks
2. DependencyAnalyzerAgent → validates dependencies
3. EstimationAgent → estimates durations
4. PriorityCalculatorAgent → calculates priorities
5. LearningPathAgent → identifies learning needs
```

---

## Inter-Agent Communication

### Message Protocol

```python
@dataclass
class AgentMessage:
    sender: str  # Agent name
    recipient: str  # Target agent or "coordinator"
    message_type: MessageType  # REQUEST | RESPONSE | NOTIFICATION
    payload: dict[str, Any]  # Structured data
    conversation_id: UUID  # For threading
    timestamp: datetime

class MessageType(Enum):
    REQUEST = "request"  # Agent requests another agent's help
    RESPONSE = "response"  # Agent responds to request
    NOTIFICATION = "notification"  # Agent broadcasts info
    ERROR = "error"  # Agent reports failure
```

### Example: TaskDecomposer requests Estimation

```python
# TaskDecomposer creates tasks, needs estimates
message = AgentMessage(
    sender="TaskDecomposerAgent",
    recipient="EstimationAgent",
    message_type=MessageType.REQUEST,
    payload={
        "action": "estimate_duration",
        "tasks": [task1, task2, task3]
    },
    conversation_id=uuid4()
)

# Coordinator routes message
response = coordinator.route_message(message)

# EstimationAgent responds
response = AgentMessage(
    sender="EstimationAgent",
    recipient="TaskDecomposerAgent",
    message_type=MessageType.RESPONSE,
    payload={
        "estimates": [
            {"task_id": task1.id, "duration_min": 45, "confidence": 0.8},
            {"task_id": task2.id, "duration_min": 60, "confidence": 0.65},
            ...
        ]
    },
    conversation_id=message.conversation_id
)
```

---

## Observability & Monitoring

### Langfuse Integration

Each agent execution logged:
```python
@observe(name="TaskDecomposerAgent.run")
def run(self, prompt: str, deps: TaskDependencies) -> DecompositionResult:
    # Agent logic...
    pass
```

### Trace Hierarchy
```
User Request
├─ Coordinator.route_request()
│  ├─ TaskDecomposerAgent.run()
│  │  ├─ create_task_tool()
│  │  ├─ create_task_tool()
│  │  └─ add_dependency_tool()
│  ├─ EstimationAgent.run()
│  │  └─ completion_repo.get_similar_tasks()
│  └─ PriorityCalculatorAgent.run()
│     └─ get_blocked_tool()
└─ Coordinator.aggregate_results()
```

### Metrics Tracked
- Agent execution time
- Tool call frequency per agent
- Success/failure rates
- Inter-agent message counts
- Parallel execution gains
- Fallback trigger rates

---

## Configuration

### Multi-Agent Settings (config.toml)

```toml
[multi_agent]
enabled = true  # Enable multi-agent system
parallel_execution = true  # Allow parallel agent runs
max_parallel_agents = 3  # Limit concurrent agents
fallback_to_general = true  # Use general agent on specialist failure
message_timeout_seconds = 30

[agents.task_decomposer]
enabled = true
model = "gpt-4o-mini"  # Can use different models per agent
max_tasks_per_goal = 10

[agents.dependency_analyzer]
enabled = true
model = "gpt-4o"  # Use stronger model for complex reasoning
max_dependency_depth = 5

[agents.estimator]
enabled = true
model = "gpt-4o-mini"
similarity_threshold = 0.7  # For finding similar past tasks
confidence_threshold = 0.5  # Minimum confidence to return estimate

[agents.priority_calculator]
enabled = true
model = "gpt-4o-mini"
# Priority algorithm weights
weight_monetary_value = 0.35
weight_time_value = 0.25
weight_alignment = 0.15
weight_risk = 0.10
weight_learning_unlock = 0.15

[agents.learning_path]
enabled = true
model = "gpt-4o"
min_tasks_to_unlock = 2  # Min tasks to justify learning
jit_window_days = 14  # Look ahead window

[agents.skill_gap_analyzer]
enabled = true
model = "gpt-4o-mini"
critical_gap_threshold = 3  # Tasks blocked to be "critical"
```

---

## Migration Strategy

### Phase 1: Foundation (Week 1)
- [ ] Create multi-agent framework (protocols, registry, coordinator)
- [ ] Implement TaskDecomposerAgent (MVP)
- [ ] Add configuration system
- [ ] Basic observability integration
- [ ] Unit tests for framework

### Phase 2: Core Specialists (Week 2)
- [ ] Implement DependencyAnalyzerAgent
- [ ] Implement EstimationAgent
- [ ] Implement PriorityCalculatorAgent
- [ ] Integration tests
- [ ] Performance benchmarks

### Phase 3: Advanced Specialists (Week 3)
- [ ] Implement LearningPathAgent
- [ ] Implement SkillGapAnalyzerAgent
- [ ] Inter-agent communication
- [ ] Parallel execution support
- [ ] End-to-end workflow tests

### Phase 4: Production (Week 4)
- [ ] Performance optimization
- [ ] Documentation
- [ ] Migration guide for users
- [ ] Feature flag rollout
- [ ] Monitoring dashboards

---

## Backward Compatibility

### Seamless Fallback
```python
# If multi-agent disabled in config
if not config.multi_agent.enabled:
    return run_single_agent(handler, db_path)  # Existing behavior

# If specialist fails
try:
    result = specialist_agent.run(prompt, deps)
except Exception as e:
    logger.warning(f"Specialist failed: {e}, falling back to general agent")
    result = general_purpose_agent.run(prompt, deps)
```

### CLI/TUI Unchanged
- No changes to `run_chat()` interface
- No changes to CLI commands
- No changes to TUI screens
- Configuration opt-in via `multi_agent.enabled = true`

---

## Testing Strategy

### Unit Tests (per agent)
```python
def test_task_decomposer_creates_tasks(mock_deps):
    agent = TaskDecomposerAgent(model="gpt-4o-mini")
    result = agent.run("Build REST API", mock_deps)
    assert len(result.tasks) > 0
    assert all(task.duration_min > 0 for task in result.tasks)
```

### Integration Tests (coordinator)
```python
async def test_coordinator_routes_to_specialist():
    coordinator = MultiAgentCoordinator(config)
    result = await coordinator.process("Create tasks for OAuth")
    assert result.agent_used == "TaskDecomposerAgent"
    assert result.success
```

### Workflow Tests (end-to-end)
```python
async def test_full_task_creation_workflow():
    coordinator = MultiAgentCoordinator(config)
    result = await coordinator.process("Add authentication feature")

    # Verify full workflow executed
    assert "TaskDecomposerAgent" in result.agents_invoked
    assert "DependencyAnalyzerAgent" in result.agents_invoked
    assert "EstimationAgent" in result.agents_invoked
    assert "PriorityCalculatorAgent" in result.agents_invoked

    # Verify results
    assert len(result.tasks_created) > 0
    assert all(task.priority > 0 for task in result.tasks_created)
```

### Performance Tests
```python
def test_parallel_execution_faster_than_sequential():
    # Compare parallel vs sequential execution
    parallel_time = timeit(coordinator.execute_parallel([agent1, agent2, agent3]))
    sequential_time = timeit(coordinator.execute_sequential([agent1, agent2, agent3]))
    assert parallel_time < sequential_time * 0.7  # At least 30% faster
```

---

## Success Metrics

### Performance
- [ ] 30%+ speedup for complex workflows (via parallelization)
- [ ] <100ms coordinator overhead
- [ ] 95%+ specialist success rate

### Quality
- [ ] 20%+ improvement in task decomposition quality (user feedback)
- [ ] 15%+ improvement in duration estimation accuracy (vs actual)
- [ ] Dependency cycle detection: 100% accuracy

### Observability
- [ ] 100% of agent calls traced in Langfuse
- [ ] <5% trace data loss
- [ ] Clear agent→tool→result lineage

### Adoption
- [ ] 0 breaking changes for existing users
- [ ] <5 min migration time (enable flag)
- [ ] 80%+ test coverage for multi-agent code

---

## Future Enhancements

### Adaptive Routing
Machine learning model to learn optimal agent routing from usage patterns.

### Agent Learning
Specialists improve over time by learning from corrections and feedback.

### Custom Specialists
User-defined specialist agents via plugin system.

### Distributed Execution
Run agents on different machines/cloud functions for extreme parallelization.

### Collaborative Agents
Multiple agents negotiate solutions for complex, ambiguous requests.

---

## References

- PydanticAI Documentation: https://ai.pydantic.dev
- Langfuse Observability: https://langfuse.com
- TaskWeaver Original Design: `/docs/`
- Multi-Agent Design Patterns: https://arxiv.org/abs/2308.08155

---

**Document Version**: 1.0.0
**Last Updated**: 2025-11-08
**Authors**: TaskWeaver Multi-Agent Team
