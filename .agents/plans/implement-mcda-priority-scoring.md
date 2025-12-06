# Feature: Multi-Criteria Priority Scoring (MCDA)

> **AUTONOMOUS PLAN**: This plan was generated with minimal user input.
> All design decisions are documented below. Review NOTES & AUTONOMOUS DECISIONS section for assumptions.

> **IMPORTANT**: Validate documentation and codebase patterns before implementing.
> Pay attention to naming of existing utils, types, and models.
> Import from correct files.

## Overview

**Description**: Implement Multi-Criteria Decision Analysis (MCDA) for intelligent task prioritization using weighted scoring across multiple dimensions (urgency, importance, effort, dependencies, age).

**Problem**: Current priority system uses simple CD3 formula (value/duration). This single-metric approach doesn't capture the full complexity of task prioritization. Users need to consider urgency vs importance, effort estimation, task age, and dependency impacts when deciding what to work on next.

**Solution**: Extend the existing priority system with multi-criteria scoring that:
- Allows users to specify urgency (1-5), importance (1-5), and effort (1-5) for each task
- Calculates weighted priority scores using configurable weights (Eisenhower Matrix integration)
- Maintains backward compatibility with existing CD3 priority calculation
- Integrates with dependency-based effective priority inheritance
- Provides CLI and agent tools for priority-aware task management

## Metadata

| Field | Value |
|-------|-------|
| Type | Enhancement |
| Complexity | Medium |
| Systems Affected | Database (schema), Models, Repository, CLI, Agent Tools |
| Dependencies | None (uses existing SQLite, Pydantic patterns) |
| Autonomy Level | Fully Autonomous |
| Assumptions Made | 7 documented assumptions |

---

## CONTEXT REFERENCES

### Mandatory Reading (READ BEFORE IMPLEMENTING)

**Database Layer:**
- `/workspace/taskweaver/src/taskweaver/database/schema.py:6-28` - Why: Schema definition pattern with CHECK constraints
- `/workspace/taskweaver/src/taskweaver/database/models.py:26-68` - Why: Task model structure and priority property pattern
- `/workspace/taskweaver/src/taskweaver/database/models.py:104-160` - Why: TaskWithDependencies and TaskWithPriority model patterns
- `/workspace/taskweaver/src/taskweaver/database/repository.py:38-75` - Why: Create method pattern with validation
- `/workspace/taskweaver/src/taskweaver/database/repository.py:183-249` - Why: Update method pattern with partial updates
- `/workspace/taskweaver/src/taskweaver/database/connection.py:94-130` - Why: Database connection context manager pattern

**Priority Calculation:**
- `/workspace/taskweaver/src/taskweaver/database/dependency_repository.py:157-223` - Why: Effective priority calculation with memoization pattern
- `/workspace/taskweaver/src/taskweaver/database/models.py:48-67` - Why: Existing priority property implementation (CD3 formula)

**CLI Patterns:**
- `/workspace/taskweaver/src/taskweaver/cli.py:33-51` - Why: Command structure with Typer annotations
- `/workspace/taskweaver/src/taskweaver/cli.py:54-86` - Why: List command with Rich table formatting
- `/workspace/taskweaver/src/taskweaver/cli.py:168-191` - Why: Show command with vertical table display

**Agent Tools:**
- `/workspace/taskweaver/src/taskweaver/agents/tools.py:61-104` - Why: Tool function signature and error handling pattern
- `/workspace/taskweaver/src/taskweaver/agents/tools.py:157-235` - Why: list_tasks_tool with response format patterns
- `/workspace/taskweaver/src/taskweaver/agents/dependencies.py:10-31` - Why: TaskDependencies container structure

**Testing:**
- `/workspace/taskweaver/src/taskweaver/database/tests/conftest.py:15-89` - Why: Fixture patterns for temp database and repositories
- `/workspace/taskweaver/src/taskweaver/database/tests/test_repository.py:216-370` - Why: Priority calculation test patterns

### New Files to Create

- `/workspace/taskweaver/src/taskweaver/database/priority_service.py` - Service for MCDA priority calculations
- `/workspace/taskweaver/src/taskweaver/database/tests/test_priority_service.py` - Unit tests for priority service
- `/workspace/taskweaver/src/taskweaver/agents/tests/test_priority_tools.py` - Integration tests for priority tools

### Documentation References

**MCDA & Prioritization:**
- [Eisenhower Matrix](https://en.wikipedia.org/wiki/Time_management#The_Eisenhower_Method) - Why: Urgency vs Importance framework
- [RICE Scoring](https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/) - Why: Reach, Impact, Confidence, Effort scoring model
- [WSJF (Weighted Shortest Job First)](https://www.scaledagileframework.com/wsjf/) - Why: Cost of Delay / Duration formula (current CD3 implementation)

**Pydantic:**
- [Pydantic Field Validation](https://docs.pydantic.dev/latest/concepts/fields/) - Why: Constraint validation patterns (ge, le)
- [Pydantic ConfigDict](https://docs.pydantic.dev/latest/api/config/) - Why: Model configuration (use_enum_values)

**SQLite:**
- [SQLite CHECK Constraints](https://www.sqlite.org/lang_createtable.html#check_constraints) - Why: Column validation at database level

### Patterns to Follow

**Naming:**
```python
# Snake case for functions, variables
def calculate_weighted_priority(self, task_id: UUID) -> float:
    urgency_score = 80.0
    weighted_result = urgency_score * weight_urgency

# PascalCase for classes
class PriorityWeights(BaseModel):
    urgency: float = 0.30

# UPPER_SNAKE_CASE for constants
DEFAULT_WEIGHTS_MCDA = {...}
SCHEMA_VERSION = 4
```

**Error Handling:**
```python
# Repository pattern: raise custom exceptions
task = self.get_task(task_id)
if task is None:
    logger.error(f"Cannot update task {task_id}: not found")
    raise TaskNotFoundError(task_id)

# Agent tool pattern: ModelRetry for LLM-fixable errors
try:
    priorities = service.calculate_priorities()
except (ValidationError, ValueError) as e:
    raise ModelRetry(str(e)) from e
```

**Logging:**
```python
# Using loguru logger
from loguru import logger

logger.debug(f"Calculating weighted priority for task {task_id}")
logger.info(f"Updated task {task_id} scores: urgency={urgency:.1f}, importance={importance:.1f}")
logger.warning(f"Task {task_id} has missing scoring data, using defaults")
logger.error(f"Failed to calculate priority for task {task_id}: {e}")
```

### Boundaries

**ALWAYS:**
- Use type hints for all functions and parameters
- Write Google-style docstrings with Args/Returns/Raises sections
- Use context managers (`with get_connection()`) for database operations
- Convert enums with `.value` for storage, reconstruct with `Enum(value)` for retrieval
- Format datetimes with `.isoformat()` for storage, `datetime.fromisoformat()` for retrieval
- Log at DEBUG (entry/details), INFO (success), WARNING (recoverable), ERROR (before raising)
- Keep functions focused (single responsibility)
- Commit incrementally during implementation
- Push after validation passes

**ASK FIRST:**
- None - all design decisions documented with rationale below

**NEVER:**
- Use bare `except:` clauses (always specify exception types)
- Modify database schema without incrementing SCHEMA_VERSION
- Skip validation commands
- Store Python objects directly in database (serialize to compatible types)
- Use mutable default arguments
- Skip type hints
- Skip docstrings for public functions/classes

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation - Database Schema & Models
**Validation**: `make type-check && make lint-check`

**Objective**: Extend database schema and Pydantic models to support MCDA scoring fields.

**Tasks:**
1. Update `SCHEMA_VERSION` to 4 in schema.py
2. Add MCDA columns to tasks table (urgency, importance, effort, priority_score, priority_updated_at)
3. Create schema migration logic for existing databases
4. Extend Task model with scoring fields
5. Create TaskCreate and TaskUpdate extensions
6. Create PriorityWeights configuration model

**Deliverables:**
- Modified schema with 5 new columns
- Migration support for v3→v4 schema
- Extended Pydantic models with validation

---

### Phase 2: Core Implementation - Priority Service
**Validation**: `make test FILE=tests/taskweaver/database/test_priority_service.py`

**Objective**: Implement business logic for multi-criteria priority calculation.

**Tasks:**
1. Create PriorityService class with repository dependencies
2. Implement `calculate_priority()` for single task
3. Implement `calculate_all_priorities()` with batch optimization
4. Implement `update_task_scores()` for user input
5. Add integration with existing effective priority calculation
6. Write comprehensive unit tests (target: 85%+ coverage)

**Deliverables:**
- Fully tested PriorityService with MCDA algorithm
- Integration with dependency-based priority inheritance
- Memoization for performance optimization

---

### Phase 3: Integration - Repository & CLI
**Validation**: `make test && make check`

**Objective**: Integrate priority scoring into repository layer and CLI commands.

**Tasks:**
1. Extend TaskRepository with `update_task_scores()` method
2. Add `list_tasks_by_priority()` with sorting options
3. Create `tw score` CLI command for priority ranking display
4. Add `--urgency`, `--importance`, `--effort` flags to `tw edit` command
5. Update `tw ls` command with `--sort priority` option
6. Enhance `tw show` command to display MCDA breakdown

**Deliverables:**
- Repository methods for score management
- CLI commands for user interaction
- Rich table formatting for priority displays

---

### Phase 4: Testing & Validation
**Validation**: `make test && coverage report --fail-under=85`

**Objective**: Ensure comprehensive test coverage and validate acceptance criteria.

**Tasks:**
1. Write integration tests for CLI commands
2. Write agent tool integration tests
3. Add edge case tests (boundary values, missing data)
4. Performance test: 1000 task priority calculation <100ms
5. Verify backward compatibility with existing CD3 priority
6. Update documentation (README, docstrings)

**Deliverables:**
- 85%+ test coverage
- All acceptance criteria verified
- Performance benchmarks documented

---

## STEP-BY-STEP TASKS

> Execute every task in order, top to bottom. Each task is atomic and testable.

### Phase 1: Foundation

#### UPDATE `/workspace/taskweaver/src/taskweaver/database/schema.py`

**Line 3: Increment schema version**
- **IMPLEMENT**: Change `SCHEMA_VERSION = 3` to `SCHEMA_VERSION = 4`
- **PATTERN**: Line 3 in schema.py
- **GOTCHA**: Must increment when adding columns
- **VALIDATE**: `grep "SCHEMA_VERSION = 4" src/taskweaver/database/schema.py`

**After line 28: Add MCDA columns to CREATE_TASKS_TABLE**
- **IMPLEMENT**: Add 5 new columns with DEFAULT values and CHECK constraints:
  ```python
  urgency INTEGER NOT NULL DEFAULT 3 CHECK (urgency BETWEEN 1 AND 5),
  importance INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
  effort INTEGER NOT NULL DEFAULT 3 CHECK (effort BETWEEN 1 AND 5),
  priority_score REAL,
  priority_updated_at TEXT,
  ```
- **PATTERN**: Lines 6-28 show CHECK constraint pattern and DEFAULT value usage
- **IMPORTS**: None needed
- **GOTCHA**: SQLite CHECK constraints must use column name, not table.column
- **VALIDATE**: `sqlite3 test.db "PRAGMA table_info(tasks);" | grep -E "(urgency|importance|effort|priority_score)"`

**After line 40: Create index for priority_score**
- **IMPLEMENT**: Add index definition for efficient priority sorting:
  ```python
  CREATE_TASKS_INDEX_PRIORITY = """
  CREATE INDEX IF NOT EXISTS idx_tasks_priority_score
  ON tasks(priority_score DESC)
  WHERE status IN ('pending', 'in_progress');
  """
  ```
- **PATTERN**: Lines 31-40 show index creation pattern
- **GOTCHA**: Partial index (WHERE clause) improves performance for active tasks only
- **VALIDATE**: `rg "CREATE_TASKS_INDEX_PRIORITY" src/taskweaver/database/schema.py`

**After line 150: Create ALTER TABLE migration statements**
- **IMPLEMENT**: Add migration support for existing v3 databases:
  ```python
  # Migration: v3 -> v4 (Add MCDA columns)
  ALTER_TASKS_ADD_URGENCY = """
  ALTER TABLE tasks ADD COLUMN urgency INTEGER NOT NULL DEFAULT 3 CHECK (urgency BETWEEN 1 AND 5);
  """

  ALTER_TASKS_ADD_IMPORTANCE = """
  ALTER TABLE tasks ADD COLUMN importance INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5);
  """

  ALTER_TASKS_ADD_EFFORT = """
  ALTER TABLE tasks ADD COLUMN effort INTEGER NOT NULL DEFAULT 3 CHECK (effort BETWEEN 1 AND 5);
  """

  ALTER_TASKS_ADD_PRIORITY_SCORE = """
  ALTER TABLE tasks ADD COLUMN priority_score REAL;
  """

  ALTER_TASKS_ADD_PRIORITY_UPDATED_AT = """
  ALTER TABLE tasks ADD COLUMN priority_updated_at TEXT;
  """
  ```
- **PATTERN**: SQLite ALTER TABLE ADD COLUMN pattern
- **GOTCHA**: CHECK constraints in ALTER TABLE statements are supported in SQLite 3.25.0+
- **VALIDATE**: `rg "ALTER_TASKS_ADD" src/taskweaver/database/schema.py`

#### UPDATE `/workspace/taskweaver/src/taskweaver/database/connection.py`

**After line 72: Add migration logic for v3→v4**
- **IMPLEMENT**: In `init_database()`, add migration detection and execution:
  ```python
  # Check existing schema version
  cursor = conn.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
  row = cursor.fetchone()
  current_version = row[0] if row else 0

  # Migrate v3 -> v4 (add MCDA columns)
  if current_version == 3:
      logger.info("Migrating database from v3 to v4 (adding MCDA columns)")
      conn.execute(ALTER_TASKS_ADD_URGENCY)
      conn.execute(ALTER_TASKS_ADD_IMPORTANCE)
      conn.execute(ALTER_TASKS_ADD_EFFORT)
      conn.execute(ALTER_TASKS_ADD_PRIORITY_SCORE)
      conn.execute(ALTER_TASKS_ADD_PRIORITY_UPDATED_AT)
      conn.execute(CREATE_TASKS_INDEX_PRIORITY)
      conn.execute(INSERT_SCHEMA_VERSION, (SCHEMA_VERSION,))
      logger.info(f"Migration complete: v3 -> v{SCHEMA_VERSION}")
  ```
- **PATTERN**: Lines 35-73 show init_database() structure
- **IMPORTS**: Import ALTER statements from schema.py
- **GOTCHA**: Migration must execute BEFORE new table creation attempts
- **VALIDATE**: Create v3 db, run init_database(), verify columns exist

**Line 63: Add priority index creation to new databases**
- **IMPLEMENT**: After `CREATE_TASKS_INDEX_STATUS`, add:
  ```python
  conn.execute(CREATE_TASKS_INDEX_PRIORITY)
  ```
- **PATTERN**: Lines 58-64 show index creation in init_database()
- **VALIDATE**: `rg "CREATE_TASKS_INDEX_PRIORITY" src/taskweaver/database/connection.py`

#### UPDATE `/workspace/taskweaver/src/taskweaver/database/models.py`

**After line 20: Add MCDA field imports**
- **IMPLEMENT**: Ensure Field is imported (already present at line 3)
- **VALIDATE**: `rg "from pydantic import.*Field" src/taskweaver/database/models.py`

**Lines 26-68: Extend Task model with MCDA fields**
- **IMPLEMENT**: Add scoring fields after `requirement` field (around line 43):
  ```python
  urgency: int = Field(default=3, ge=1, le=5, description="Urgency score (1=low, 5=high)")
  importance: int = Field(default=3, ge=1, le=5, description="Importance score (1=low, 5=high)")
  effort: int = Field(default=3, ge=1, le=5, description="Effort score (1=easy, 5=hard)")
  priority_score: float | None = Field(default=None, description="Calculated MCDA priority score (0-100)")
  priority_updated_at: datetime | None = Field(default=None, description="When priority was last calculated")
  ```
- **PATTERN**: Lines 26-44 show field definition pattern with Field() and constraints
- **GOTCHA**: Use `ge=1, le=5` for Pydantic validation matching SQLite CHECK constraints
- **VALIDATE**: `rg "urgency: int.*Field" src/taskweaver/database/models.py`

**After line 67: Add weighted_priority property**
- **IMPLEMENT**: Add new property after existing `priority` property:
  ```python
  @property
  def weighted_priority(self) -> float:
      """Calculate weighted MCDA priority score.

      Uses RICE-inspired formula:
      - Urgency (0.30): Time sensitivity
      - Importance (0.35): Strategic value
      - Effort inverse (0.20): Prefer easier tasks (6-effort for inversion)
      - Dependencies (0.10): Blocked task count (requires external data)
      - Age (0.05): Days since creation

      Returns:
          Weighted priority score (0-100 range). Returns cached priority_score
          if available, otherwise calculates on-the-fly without dependencies/age.

      Note:
          For full MCDA calculation including dependencies and age,
          use PriorityService.calculate_priority() instead.
      """
      # Return cached score if available
      if self.priority_score is not None:
          return self.priority_score

      # Fallback: calculate basic weighted score (no dependencies/age)
      # Normalize 1-5 scores to 0-100 scale: (value - 1) / 4 * 100
      urgency_norm = (self.urgency - 1) / 4 * 100
      importance_norm = (self.importance - 1) / 4 * 100
      effort_norm = (6 - self.effort - 1) / 4 * 100  # Invert: lower effort = higher score

      # Default weights (without dependencies/age which need external data)
      # Adjusted to sum to 1.0 without dep/age components
      weighted = (
          urgency_norm * 0.33 +      # 0.30 / 0.90
          importance_norm * 0.39 +   # 0.35 / 0.90
          effort_norm * 0.28         # 0.25 / 0.90
      )

      return round(weighted, 2)
  ```
- **PATTERN**: Lines 48-67 show @property decorator pattern for priority
- **GOTCHA**: This is simplified calculation; full calculation in PriorityService
- **VALIDATE**: Create task, access task.weighted_priority, verify returns float

**Lines 70-78: Extend TaskCreate with MCDA fields**
- **IMPLEMENT**: Add optional scoring fields to TaskCreate:
  ```python
  urgency: int = Field(default=3, ge=1, le=5)
  importance: int = Field(default=3, ge=1, le=5)
  effort: int = Field(default=3, ge=1, le=5)
  ```
- **PATTERN**: Lines 70-78 show TaskCreate structure with defaults
- **GOTCHA**: Use defaults so existing code doesn't break
- **VALIDATE**: Create TaskCreate without scores, verify defaults work

**Lines 80-93: Extend TaskUpdate with MCDA fields**
- **IMPLEMENT**: Add optional scoring fields to TaskUpdate (all None by default):
  ```python
  urgency: int | None = Field(default=None, ge=1, le=5)
  importance: int | None = Field(default=None, ge=1, le=5)
  effort: int | None = Field(default=None, ge=1, le=5)
  ```
- **PATTERN**: Lines 80-93 show TaskUpdate with all optional fields (None defaults)
- **VALIDATE**: Create TaskUpdate with only urgency, verify other fields remain None

**After line 160: Create PriorityWeights model**
- **IMPLEMENT**: Add configuration model for MCDA weights:
  ```python
  class PriorityWeights(BaseModel):
      """Configurable weights for MCDA priority calculation.

      All weights must be non-negative and should sum to 1.0 for normalized scoring.
      Based on RICE framework with dependencies and age factors.
      """

      urgency: float = Field(
          default=0.30,
          ge=0.0,
          le=1.0,
          description="Weight for urgency score (time sensitivity)"
      )
      importance: float = Field(
          default=0.35,
          ge=0.0,
          le=1.0,
          description="Weight for importance score (strategic value)"
      )
      effort: float = Field(
          default=0.20,
          ge=0.0,
          le=1.0,
          description="Weight for effort inverse (prefer easier tasks)"
      )
      dependencies: float = Field(
          default=0.10,
          ge=0.0,
          le=1.0,
          description="Weight for dependency count (blocked tasks)"
      )
      age: float = Field(
          default=0.05,
          ge=0.0,
          le=1.0,
          description="Weight for task age (days since creation)"
      )

      @property
      def total_weight(self) -> float:
          """Calculate sum of all weights (should be 1.0 for normalized scores)."""
          return self.urgency + self.importance + self.effort + self.dependencies + self.age

      def validate_weights(self) -> None:
          """Validate that weights sum to approximately 1.0.

          Raises:
              ValueError: If weights don't sum to 1.0 (within 0.01 tolerance).
          """
          if abs(self.total_weight - 1.0) > 0.01:
              raise ValueError(
                  f"Weights must sum to 1.0, got {self.total_weight:.3f}. "
                  f"Current: urgency={self.urgency}, importance={self.importance}, "
                  f"effort={self.effort}, dependencies={self.dependencies}, age={self.age}"
              )
  ```
- **PATTERN**: Lines 26-68 show BaseModel pattern with Field descriptors
- **GOTCHA**: Weights don't auto-validate sum; validate_weights() must be called explicitly
- **VALIDATE**: Create PriorityWeights(), call validate_weights(), verify passes

### Phase 2: Core Implementation

#### CREATE `/workspace/taskweaver/src/taskweaver/database/priority_service.py`

**Lines 1-20: Imports and setup**
- **IMPLEMENT**: Import all necessary dependencies:
  ```python
  """Priority service for multi-criteria decision analysis (MCDA).

  Implements weighted scoring for task prioritization using:
  - User-defined scores: urgency, importance, effort
  - System-calculated factors: dependency count, task age
  - Configurable weights (RICE framework variant)

  Integrates with existing CD3 priority and DAG-based effective priority.
  """

  from datetime import UTC, datetime
  from pathlib import Path
  from uuid import UUID

  from loguru import logger

  from taskweaver.config import get_paths
  from taskweaver.database.exceptions import TaskNotFoundError
  from taskweaver.database.models import PriorityWeights, Task, TaskWithDependencies
  from taskweaver.database.repository import TaskRepository
  from taskweaver.database.dependency_repository import TaskDependencyRepository
  from taskweaver.database.connection import DEFAULT_DB_PATH
  ```
- **PATTERN**: Standard imports organization (stdlib, third-party, local)
- **VALIDATE**: `make lint-check`

**Lines 22-50: PriorityService class definition**
- **IMPLEMENT**: Create service class with repository dependencies:
  ```python
  class PriorityService:
      """Service for multi-criteria priority scoring.

      Calculates weighted priority scores combining user inputs (urgency,
      importance, effort) with system factors (dependencies, age).

      Attributes:
          db_path: Path to SQLite database.
          task_repo: Repository for task CRUD operations.
          dep_repo: Repository for dependency data.
          weights: MCDA weight configuration.
      """

      def __init__(
          self,
          db_path: Path = DEFAULT_DB_PATH,
          weights: PriorityWeights | None = None,
      ) -> None:
          """Initialize priority service.

          Args:
              db_path: Path to task database.
              weights: Custom MCDA weights. Defaults to RICE-inspired weights.

          Raises:
              ValueError: If custom weights don't sum to 1.0.
          """
          self.db_path = db_path
          self.task_repo = TaskRepository(db_path)
          self.dep_repo = TaskDependencyRepository(db_path)

          # Use default weights if not provided
          self.weights = weights if weights is not None else PriorityWeights()
          self.weights.validate_weights()

          logger.debug(
              f"PriorityService initialized with database: {db_path}, "
              f"weights: urgency={self.weights.urgency}, importance={self.weights.importance}, "
              f"effort={self.weights.effort}, dependencies={self.weights.dependencies}, age={self.weights.age}"
          )
  ```
- **PATTERN**: Lines 28-36 in repository.py show __init__ pattern with db_path
- **GOTCHA**: Validate weights immediately to fail fast
- **VALIDATE**: Instantiate PriorityService(), verify no errors

**Lines 52-130: calculate_priority method**
- **IMPLEMENT**: Core MCDA calculation for single task:
  ```python
  def calculate_priority(self, task_id: UUID) -> float:
      """Calculate weighted MCDA priority for a single task.

      Formula (normalized to 0-100):
          weighted_score = (
              (urgency_norm * W_urgency) +
              (importance_norm * W_importance) +
              (effort_inverse_norm * W_effort) +
              (dependency_count_norm * W_dependencies) +
              (age_norm * W_age)
          )

      Where:
          - urgency_norm = (urgency - 1) / 4 * 100  (1-5 scale -> 0-100)
          - importance_norm = (importance - 1) / 4 * 100
          - effort_inverse_norm = ((6 - effort) - 1) / 4 * 100  (inverted)
          - dependency_count_norm = min(dependency_count / 10 * 100, 100)
          - age_norm = min(age_days / 30 * 100, 100)

      Args:
          task_id: UUID of task to score.

      Returns:
          Weighted priority score (0-100).

      Raises:
          TaskNotFoundError: If task doesn't exist.
      """
      logger.debug(f"Calculating MCDA priority for task {task_id}")

      # Get task data
      task = self.task_repo.get_task(task_id)
      if task is None:
          logger.error(f"Cannot calculate priority for task {task_id}: not found")
          raise TaskNotFoundError(task_id)

      # Get dependency data
      blocked_tasks = self.dep_repo.get_blocked(task_id)
      dependency_count = len(blocked_tasks)

      # Calculate age in days
      age_days = (datetime.now(UTC) - task.created_at).total_seconds() / 86400

      # Normalize scores to 0-100 scale
      urgency_norm = (task.urgency - 1) / 4 * 100
      importance_norm = (task.importance - 1) / 4 * 100
      effort_inverse_norm = ((6 - task.effort) - 1) / 4 * 100  # Invert: lower effort = higher score

      # Normalize dependency count (cap at 10 dependencies = 100 score)
      dependency_norm = min(dependency_count / 10 * 100, 100.0)

      # Normalize age (cap at 30 days = 100 score)
      age_norm = min(age_days / 30 * 100, 100.0)

      # Calculate weighted score
      weighted_score = (
          urgency_norm * self.weights.urgency +
          importance_norm * self.weights.importance +
          effort_inverse_norm * self.weights.effort +
          dependency_norm * self.weights.dependencies +
          age_norm * self.weights.age
      )

      # Round to 2 decimal places
      final_score = round(weighted_score, 2)

      logger.debug(
          f"Task {task_id} MCDA components: "
          f"urgency={urgency_norm:.1f}, importance={importance_norm:.1f}, "
          f"effort_inv={effort_inverse_norm:.1f}, deps={dependency_norm:.1f}, "
          f"age={age_norm:.1f} -> weighted={final_score:.2f}"
      )

      return final_score
  ```
- **PATTERN**: Lines 157-223 in dependency_repository.py show complex calculation pattern
- **GOTCHA**: Effort must be inverted (6 - effort) so lower effort = higher priority
- **VALIDATE**: Create test task, calculate priority, verify result in 0-100 range

**Lines 132-200: update_task_priority method**
- **IMPLEMENT**: Calculate and persist priority score to database:
  ```python
  def update_task_priority(self, task_id: UUID) -> Task:
      """Calculate priority and update task record.

      Updates both priority_score and priority_updated_at fields.

      Args:
          task_id: UUID of task to update.

      Returns:
          Updated task with new priority_score.

      Raises:
          TaskNotFoundError: If task doesn't exist.
      """
      logger.debug(f"Updating priority for task {task_id}")

      # Calculate new priority score
      priority_score = self.calculate_priority(task_id)

      # Update task in database
      task = self.task_repo.get_task(task_id)
      if task is None:
          raise TaskNotFoundError(task_id)

      # Direct database update (more efficient than TaskUpdate)
      from taskweaver.database.connection import get_connection
      with get_connection(self.db_path) as conn:
          conn.execute(
              """
              UPDATE tasks
              SET priority_score = ?, priority_updated_at = ?
              WHERE task_id = ?
              """,
              (priority_score, datetime.now(UTC).isoformat(), str(task_id)),
          )
          conn.commit()

      # Refresh task from database
      task = self.task_repo.get_task(task_id)
      logger.info(
          f"Updated task {task_id} priority: score={priority_score:.2f}, "
          f"urgency={task.urgency}, importance={task.importance}, effort={task.effort}"
      )

      return task
  ```
- **PATTERN**: Lines 183-249 in repository.py show update pattern
- **GOTCHA**: Use direct SQL for performance (avoid full TaskUpdate model)
- **VALIDATE**: Update priority, verify priority_score and priority_updated_at are set

**Lines 202-280: calculate_all_priorities method**
- **IMPLEMENT**: Batch calculation with memoization:
  ```python
  def calculate_all_priorities(
      self,
      status: str | None = None,
  ) -> dict[UUID, float]:
      """Calculate priorities for all tasks (or filtered by status).

      Uses batch processing for efficiency - fetches all tasks once,
      then calculates scores without repeated database queries.

      Args:
          status: Optional status filter (pending, in_progress, completed, cancelled).

      Returns:
          Dict mapping task_id to priority_score.
      """
      logger.debug(f"Calculating priorities for all tasks (status filter: {status})")

      # Get tasks with dependency data
      from taskweaver.database.models import TaskStatus
      task_status = TaskStatus(status) if status else None
      tasks = self.dep_repo.list_tasks_with_deps(status=task_status)

      if not tasks:
          logger.info("No tasks to calculate priorities for")
          return {}

      # Calculate priorities for all tasks
      priorities: dict[UUID, float] = {}

      for task in tasks:
          # Get blocked task count (already loaded in TaskWithDependencies)
          dependency_count = task.tasks_blocked_count

          # Calculate age
          age_days = (datetime.now(UTC) - task.created_at).total_seconds() / 86400

          # Normalize scores
          urgency_norm = (task.urgency - 1) / 4 * 100
          importance_norm = (task.importance - 1) / 4 * 100
          effort_inverse_norm = ((6 - task.effort) - 1) / 4 * 100
          dependency_norm = min(dependency_count / 10 * 100, 100.0)
          age_norm = min(age_days / 30 * 100, 100.0)

          # Calculate weighted score
          weighted_score = (
              urgency_norm * self.weights.urgency +
              importance_norm * self.weights.importance +
              effort_inverse_norm * self.weights.effort +
              dependency_norm * self.weights.dependencies +
              age_norm * self.weights.age
          )

          priorities[task.task_id] = round(weighted_score, 2)

      logger.info(f"Calculated priorities for {len(priorities)} task(s)")
      return priorities
  ```
- **PATTERN**: Lines 157-223 in dependency_repository.py show batch calculation pattern
- **GOTCHA**: Use list_tasks_with_deps() to avoid N+1 queries for dependency counts
- **VALIDATE**: Calculate all priorities, verify dict returned with correct count

**Lines 282-340: update_all_priorities method**
- **IMPLEMENT**: Batch update priorities in database:
  ```python
  def update_all_priorities(self, status: str | None = None) -> int:
      """Calculate and persist priorities for all tasks.

      Efficient batch operation that calculates all scores, then
      updates database in a single transaction.

      Args:
          status: Optional status filter for which tasks to update.

      Returns:
          Number of tasks updated.
      """
      logger.debug(f"Batch updating priorities (status filter: {status})")

      # Calculate all priorities
      priorities = self.calculate_all_priorities(status=status)

      if not priorities:
          return 0

      # Batch update in single transaction
      from taskweaver.database.connection import get_connection

      updated_at = datetime.now(UTC).isoformat()
      update_count = 0

      with get_connection(self.db_path) as conn:
          for task_id, priority_score in priorities.items():
              conn.execute(
                  """
                  UPDATE tasks
                  SET priority_score = ?, priority_updated_at = ?
                  WHERE task_id = ?
                  """,
                  (priority_score, updated_at, str(task_id)),
              )
              update_count += 1

          conn.commit()

      logger.info(f"Batch updated {update_count} task priorities")
      return update_count
  ```
- **PATTERN**: Batch operations with single transaction for atomicity
- **GOTCHA**: Use single timestamp for all updates in batch
- **VALIDATE**: Run batch update, verify all tasks have updated priority_updated_at

#### UPDATE `/workspace/taskweaver/src/taskweaver/database/repository.py`

**After line 249: Add update_task_scores method**
- **IMPLEMENT**: Convenience method for updating MCDA scores:
  ```python
  def update_task_scores(
      self,
      task_id: UUID,
      urgency: int | None = None,
      importance: int | None = None,
      effort: int | None = None,
      recalculate_priority: bool = True,
  ) -> Task:
      """Update task MCDA scores and optionally recalculate priority.

      Convenience method for updating scoring fields without using TaskUpdate.

      Args:
          task_id: UUID of task to update.
          urgency: New urgency score (1-5), or None to keep current.
          importance: New importance score (1-5), or None to keep current.
          effort: New effort score (1-5), or None to keep current.
          recalculate_priority: If True, recalculates priority_score after update.

      Returns:
          Updated task.

      Raises:
          TaskNotFoundError: If task doesn't exist.
          ValueError: If any score is outside 1-5 range.
      """
      logger.debug(f"Updating scores for task {task_id}")

      # Validate task exists
      task = self.get_task(task_id)
      if task is None:
          logger.error(f"Cannot update scores for task {task_id}: not found")
          raise TaskNotFoundError(task_id)

      # Validate score ranges
      if urgency is not None and not 1 <= urgency <= 5:
          raise ValueError(f"urgency must be 1-5, got {urgency}")
      if importance is not None and not 1 <= importance <= 5:
          raise ValueError(f"importance must be 1-5, got {importance}")
      if effort is not None and not 1 <= effort <= 5:
          raise ValueError(f"effort must be 1-5, got {effort}")

      # Build update dict
      changes = []
      if urgency is not None:
          changes.append(f"urgency: {task.urgency} -> {urgency}")
          task.urgency = urgency
      if importance is not None:
          changes.append(f"importance: {task.importance} -> {importance}")
          task.importance = importance
      if effort is not None:
          changes.append(f"effort: {task.effort} -> {effort}")
          task.effort = effort

      # Update timestamp
      task.updated_at = datetime.now(UTC)

      # Persist to database
      with get_connection(self.db_path) as conn:
          conn.execute(
              """
              UPDATE tasks
              SET urgency = ?, importance = ?, effort = ?, updated_at = ?
              WHERE task_id = ?
              """,
              (task.urgency, task.importance, task.effort, task.updated_at.isoformat(), str(task_id)),
          )
          conn.commit()

      logger.info(f"Updated task {task_id} scores: {', '.join(changes)}")

      # Recalculate priority if requested
      if recalculate_priority and changes:
          from taskweaver.database.priority_service import PriorityService
          service = PriorityService(self.db_path)
          task = service.update_task_priority(task_id)

      return task
  ```
- **PATTERN**: Lines 183-249 show update method pattern
- **IMPORTS**: Add `from datetime import UTC, datetime` if not present
- **GOTCHA**: Circular import with PriorityService - import inside method
- **VALIDATE**: Update scores, verify task updated and priority recalculated

**After line 148: Add list_tasks_by_priority method**
- **IMPLEMENT**: Query tasks sorted by priority_score:
  ```python
  def list_tasks_by_priority(
      self,
      status: TaskStatus | None = None,
      limit: int | None = None,
      ascending: bool = False,
  ) -> list[Task]:
      """List tasks ordered by MCDA priority score.

      Args:
          status: Optional status filter.
          limit: Maximum number of tasks to return.
          ascending: If True, sort low-to-high. If False, high-to-low (default).

      Returns:
          List of tasks sorted by priority_score.

      Note:
          Tasks with NULL priority_score are sorted last (regardless of direction).
      """
      filter_msg = f"status={status.value}" if status else "no filter"
      order = "ASC" if ascending else "DESC"
      logger.debug(f"Listing tasks by priority ({filter_msg}, order={order}, limit={limit})")

      # Build query
      query = """
          SELECT * FROM tasks
          WHERE 1=1
          {status_filter}
          ORDER BY
              CASE WHEN priority_score IS NULL THEN 1 ELSE 0 END,
              priority_score {order}
          {limit_clause}
      """

      status_filter = f"AND status = ?" if status else ""
      limit_clause = f"LIMIT {limit}" if limit else ""

      query = query.format(
          status_filter=status_filter,
          order=order,
          limit_clause=limit_clause,
      )

      # Execute query
      with get_connection(self.db_path) as conn:
          if status:
              cursor = conn.execute(query, (status.value,))
          else:
              cursor = conn.execute(query)

          rows = cursor.fetchall()

      logger.info(f"Retrieved {len(rows)} task(s) by priority ({filter_msg})")

      # Reconstruct Task objects
      return [
          Task(
              task_id=UUID(row["task_id"]),
              title=row["title"],
              description=row["description"],
              status=TaskStatus(row["status"]),
              created_at=datetime.fromisoformat(row["created_at"]),
              updated_at=datetime.fromisoformat(row["updated_at"]),
              duration_min=row["duration_min"],
              llm_value=row["llm_value"],
              requirement=row["requirement"],
              urgency=row["urgency"],
              importance=row["importance"],
              effort=row["effort"],
              priority_score=row["priority_score"],
              priority_updated_at=(
                  datetime.fromisoformat(row["priority_updated_at"])
                  if row["priority_updated_at"]
                  else None
              ),
          )
          for row in rows
      ]
  ```
- **PATTERN**: Lines 109-148 show list_tasks pattern with SQL query
- **GOTCHA**: NULL priority_score tasks sorted last using CASE expression
- **VALIDATE**: Create tasks, set some priorities, list by priority, verify order

### Phase 3: CLI Integration

#### UPDATE `/workspace/taskweaver/src/taskweaver/cli.py`

**After line 340: Add score command**
- **IMPLEMENT**: Create new CLI command for priority ranking:
  ```python
  @app.command(name="score", help="Display tasks ranked by MCDA priority score")
  def score_command(
      limit: Annotated[int, typer.Option("--limit", "-l", help="Max tasks to display (1-100)")] = 10,
      status: Annotated[
          str | None,
          typer.Option("--status", "-s", help="Filter: pending, in_progress, completed, cancelled"),
      ] = None,
      recalculate: Annotated[bool, typer.Option("--recalc", help="Recalculate all priorities first")] = False,
      db_path: Annotated[Path, typer.Option("--db", help="Database path")] = DEFAULT_DB,
  ) -> None:
      """Display tasks ranked by MCDA priority score.

      Shows multi-criteria scoring breakdown including urgency, importance,
      effort, dependencies, and age factors.

      Example:
          tw score --limit 5 --status pending
          tw score --recalc  # Recalculate before displaying
      """
      from taskweaver.database.priority_service import PriorityService
      from taskweaver.database.models import TaskStatus

      # Recalculate priorities if requested
      if recalculate:
          console.print("[yellow]Recalculating priorities...[/yellow]")
          service = PriorityService(db_path)
          task_status_filter = status if status is None else TaskStatus(status)
          updated_count = service.update_all_priorities(status=task_status_filter)
          console.print(f"[green]✓[/green] Updated {updated_count} task(s)")

      # Fetch tasks sorted by priority
      task_repo = TaskRepository(db_path)
      task_status = TaskStatus(status) if status else None
      tasks = task_repo.list_tasks_by_priority(status=task_status, limit=limit)

      if not tasks:
          console.print("[yellow]No tasks found[/yellow]")
          return

      # Create Rich table
      from rich.table import Table

      table = Table(title="⭐ Task Priority Scores", show_lines=True)
      table.add_column("#", style="dim", width=3)
      table.add_column("Title", style="bold cyan", width=35)
      table.add_column("Priority", style="bold yellow", justify="right", width=10)
      table.add_column("U/I/E", style="dim", justify="center", width=7)
      table.add_column("Status", style="dim", width=12)
      table.add_column("CD3", justify="right", width=8)

      # Add rows
      for i, task in enumerate(tasks, start=1):
          # Priority score (or "N/A" if not calculated)
          priority_str = f"{task.priority_score:.1f}" if task.priority_score is not None else "N/A"

          # UrgencyImportanceEffort short form
          uie_str = f"{task.urgency}/{task.importance}/{task.effort}"

          # CD3 priority for comparison
          cd3_str = f"{task.priority:.2f}"

          # Emoji indicator for priority level
          if task.priority_score is not None:
              if task.priority_score >= 75:
                  emoji = "🔥"
              elif task.priority_score >= 50:
                  emoji = "⚡"
              elif task.priority_score >= 25:
                  emoji = "⏳"
              else:
                  emoji = "❄️"
              rank_str = f"{emoji} {i}"
          else:
              rank_str = str(i)

          table.add_row(
              rank_str,
              task.title[:35],
              priority_str,
              uie_str,
              str(task.status.value),
              cd3_str,
          )

      console.print(table)
      console.print(
          f"\n[dim]Showing {len(tasks)} task(s). "
          f"U/I/E = Urgency/Importance/Effort (1-5 scale). "
          f"CD3 = Current value/duration priority.[/dim]"
      )
  ```
- **PATTERN**: Lines 54-86 show list command with Rich table
- **IMPORTS**: TaskRepository, PriorityService, TaskStatus, Table
- **GOTCHA**: Use emoji indicators for quick visual scanning
- **VALIDATE**: `tw score --limit 3`, verify table displays correctly

**Lines 118-162: Update edit command with scoring flags**
- **IMPLEMENT**: Add urgency, importance, effort options to existing edit command:
  ```python
  # Find existing edit command and add these parameters after requirement parameter:
  urgency: Annotated[int | None, typer.Option("--urgency", "-u", help="Urgency score (1=low, 5=high)")] = None,
  importance: Annotated[int | None, typer.Option("--importance", "-i", help="Importance score (1=low, 5=high)")] = None,
  effort: Annotated[int | None, typer.Option("--effort", "-e", help="Effort score (1=easy, 5=hard)")] = None,
  ```

  # In the validation section (around line 135), add:
  ```python
  if not any([title, description, status, duration_min, llm_value, requirement, urgency, importance, effort]):
      console.print("[red]Error: Must specify at least one field to update[/red]")
      raise typer.Exit(code=1)
  ```

  # In the TaskUpdate construction (around line 139), add:
  ```python
  update_data = TaskUpdate(
      title=title,
      description=description,
      status=TaskStatus(status) if status else None,
      duration_min=duration_min,
      llm_value=llm_value,
      requirement=requirement,
      urgency=urgency,
      importance=importance,
      effort=effort,
  )
  ```

  # After task update (around line 152), add priority recalculation:
  ```python
  updated_task = task_repo.update_task(task_id, update_data)

  # Recalculate priority if scoring fields changed
  if any([urgency is not None, importance is not None, effort is not None]):
      from taskweaver.database.priority_service import PriorityService
      service = PriorityService(db_path)
      updated_task = service.update_task_priority(task_id)
      console.print(f"[dim]Priority recalculated: {updated_task.priority_score:.1f}[/dim]")

  console.print(f"✅ Updated task: [cyan]{task_id}[/cyan]")
  ```
- **PATTERN**: Lines 118-162 show edit command structure
- **GOTCHA**: Recalculate priority after scoring updates
- **VALIDATE**: `tw edit <task-id> --urgency 5 --importance 4`, verify priority updated

**Lines 54-86: Update ls command with --sort priority option**
- **IMPLEMENT**: Add priority sorting to list command:
  ```python
  # Add parameter to ls command (around line 58):
  sort: Annotated[
      str | None,
      typer.Option("--sort", help="Sort by: created, priority, score"),
  ] = None,

  # Update list_tasks call (around line 72):
  if sort == "priority":
      # Sort by CD3 priority (value/duration)
      task_list = task_repo.list_tasks(status=status)
      task_list = sorted(task_list, key=lambda t: t.priority, reverse=True)
  elif sort == "score":
      # Sort by MCDA priority_score
      task_list = task_repo.list_tasks_by_priority(status=status)
  else:
      # Default: sort by created_at DESC
      task_list = task_repo.list_tasks(status=status)
  ```
- **PATTERN**: Lines 54-86 show ls command
- **GOTCHA**: Distinguish between "priority" (CD3) and "score" (MCDA)
- **VALIDATE**: `tw ls --sort score`, verify MCDA ordering

**Lines 168-191: Update show command with MCDA breakdown**
- **IMPLEMENT**: Add priority breakdown to show command output:
  ```python
  # After the main task table (around line 189), add:
  console.print(table)

  # Add MCDA breakdown if priority_score exists
  if task.priority_score is not None:
      from rich.table import Table

      breakdown_table = Table(
          title="📊 MCDA Priority Breakdown",
          show_header=False,
          show_lines=True,
          width=60,
      )
      breakdown_table.add_column("Component", style="bold cyan")
      breakdown_table.add_column("Score", justify="right")
      breakdown_table.add_column("Weight", justify="right", style="dim")

      # Calculate component contributions
      urgency_norm = (task.urgency - 1) / 4 * 100
      importance_norm = (task.importance - 1) / 4 * 100
      effort_inv_norm = ((6 - task.effort) - 1) / 4 * 100

      breakdown_table.add_row("Urgency", f"{urgency_norm:.1f}", "× 0.30")
      breakdown_table.add_row("Importance", f"{importance_norm:.1f}", "× 0.35")
      breakdown_table.add_row("Effort (inverse)", f"{effort_inv_norm:.1f}", "× 0.20")
      breakdown_table.add_row("Dependencies", "~", "× 0.10")
      breakdown_table.add_row("Age", "~", "× 0.05")
      breakdown_table.add_row("[bold]Total[/bold]", f"[bold]{task.priority_score:.1f}[/bold]", "")

      console.print(breakdown_table)
      console.print(f"\n[dim]Updated: {task.priority_updated_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
  ```
- **PATTERN**: Lines 168-191 show show command with vertical table
- **GOTCHA**: Only show breakdown if priority_score exists (not all tasks will have it)
- **VALIDATE**: `tw show <task-id>`, verify MCDA breakdown displays

### Phase 4: Agent Tool Integration

#### UPDATE `/workspace/taskweaver/src/taskweaver/agents/tools.py`

**After line 796 (after calculator_tool): Add score_tasks_tool**
- **IMPLEMENT**: Create agent tool for priority scoring:
  ```python
  def score_tasks_tool(
      ctx: RunContext[TaskDependencies],
      status: str | None = None,
      sort_by: str = "score",
      limit: int = 10,
      response_format: str = "concise",
  ) -> str | dict:
      """Score and rank tasks by MCDA priority.

      Provides intelligent task prioritization using multi-criteria scoring:
      - Urgency: Time sensitivity (1-5)
      - Importance: Strategic value (1-5)
      - Effort: Complexity/duration (1-5)
      - Dependencies: Number of blocked tasks
      - Age: Days since creation

      Use this tool when user asks about:
      - "What should I work on next?"
      - "Which tasks are most important?"
      - "Show me high priority tasks"
      - "What are my top priorities?"

      Args:
          ctx: Runtime context with TaskDependencies.
          status: Optional filter (pending, in_progress, completed, cancelled).
          sort_by: Sort metric: score (MCDA), priority (CD3), created, duration.
          limit: Max tasks to return (default 10, max 50).
          response_format: Output format: concise (chat) or detailed (tool chaining).

      Returns:
          If concise: Formatted ranking string with MCDA scores.
          If detailed: Dict with tasks, metadata, recommendations.

      Raises:
          ModelRetry: If parameters invalid.

      Example:
          >>> score_tasks_tool(ctx, status="pending", limit=5)
          "📊 Top 5 Priorities:\\n1. Fix auth bug (score: 87.3, U:5 I:5 E:2)\\n..."
      """
      # Validate sort_by
      valid_sort = ["score", "priority", "created", "duration"]
      if sort_by not in valid_sort:
          raise ModelRetry(
              f"Invalid sort_by: '{sort_by}'. Use one of: {', '.join(valid_sort)}"
          ) from None

      # Validate response_format
      try:
          fmt = ResponseFormat(response_format)
      except ValueError:
          raise ModelRetry(
              f"Invalid response_format: '{response_format}'. Use: concise, detailed"
          ) from None

      # Parse status
      from taskweaver.database.models import TaskStatus
      try:
          task_status = TaskStatus(status) if status else None
      except ValueError:
          raise ModelRetry(
              f"Invalid status: '{status}'. Use: pending, in_progress, completed, cancelled"
          ) from None

      # Get tasks based on sort preference
      if sort_by == "score":
          # MCDA priority score
          tasks = ctx.deps.task_repo.list_tasks_by_priority(
              status=task_status,
              limit=min(limit, 50),
          )
      elif sort_by == "priority":
          # CD3 priority (value/duration)
          tasks = ctx.deps.task_repo.list_tasks(status=task_status)
          tasks = sorted(tasks, key=lambda t: t.priority, reverse=True)[:min(limit, 50)]
      elif sort_by == "created":
          tasks = ctx.deps.task_repo.list_tasks(status=task_status)
          tasks = sorted(tasks, key=lambda t: t.created_at, reverse=True)[:min(limit, 50)]
      else:  # duration
          tasks = ctx.deps.task_repo.list_tasks(status=task_status)
          tasks = sorted(tasks, key=lambda t: t.duration_min)[:min(limit, 50)]

      if not tasks:
          status_str = f" with status '{status}'" if status else ""
          return f"No tasks found{status_str}."

      # Format response
      if fmt == ResponseFormat.CONCISE:
          lines = [f"📊 Top {len(tasks)} Priorities (sorted by {sort_by}):\n"]

          for i, task in enumerate(tasks, start=1):
              # MCDA score display
              score_str = f"{task.priority_score:.1f}" if task.priority_score else "N/A"

              # UrgencyImportanceEffort breakdown
              uie_str = f"U:{task.urgency} I:{task.importance} E:{task.effort}"

              # CD3 for comparison
              cd3_str = f"CD3:{task.priority:.2f}"

              lines.append(
                  f"{i}. {task.title[:40]} "
                  f"(score: {score_str}, {uie_str}, {cd3_str}, "
                  f"{task.duration_min}min, {task.status.value})"
              )

          return "\n".join(lines)

      # Detailed format for tool chaining
      return {
          "tasks": tasks,
          "total_count": len(tasks),
          "sort_by": sort_by,
          "has_scores": any(t.priority_score is not None for t in tasks),
          "suggestion": (
              f"Top {min(len(tasks), 3)} tasks are ready to start. "
              f"Recommend starting with highest score task."
              if tasks
              else None
          ),
      }
  ```
- **PATTERN**: Lines 157-235 show list_tasks_tool structure
- **IMPORTS**: ResponseFormat, TaskStatus
- **GOTCHA**: Handle both scored and unscored tasks gracefully
- **VALIDATE**: Call tool with ctx, verify formatted output

**After score_tasks_tool: Add update_task_scores_tool**
- **IMPLEMENT**: Create tool for updating MCDA scores:
  ```python
  def update_task_scores_tool(
      ctx: RunContext[TaskDependencies],
      task_id: UUID,
      urgency: int | None = None,
      importance: int | None = None,
      effort: int | None = None,
  ) -> str:
      """Update MCDA scoring factors for a task.

      Use this tool when user wants to set or change task priority factors.
      After updating scores, priority_score is automatically recalculated.

      Scoring Guide:
      - Urgency (1-5): How time-sensitive is this task?
          1 = Can wait months, 5 = Critical/urgent
      - Importance (1-5): How valuable is completing this task?
          1 = Nice to have, 5 = Critical business value
      - Effort (1-5): How complex/time-consuming is this task?
          1 = Quick/easy, 5 = Very complex/long

      Args:
          ctx: Runtime context with TaskDependencies.
          task_id: UUID of task to update.
          urgency: Urgency score (1-5). None keeps current value.
          importance: Importance score (1-5). None keeps current value.
          effort: Effort score (1-5). None keeps current value.

      Returns:
          Confirmation message with updated priority score.

      Raises:
          ModelRetry: If task not found or scores invalid (must be 1-5).

      Example:
          >>> update_task_scores_tool(ctx, task_id, urgency=5, importance=4, effort=2)
          "✅ Updated scores for 'Fix auth bug': urgency=5, importance=4, effort=2. New priority: 87.3"
      """
      try:
          # Update scores using repository method
          task = ctx.deps.task_repo.update_task_scores(
              task_id=task_id,
              urgency=urgency,
              importance=importance,
              effort=effort,
              recalculate_priority=True,
          )

          # Format success message
          score_parts = []
          if urgency is not None:
              score_parts.append(f"urgency={urgency}")
          if importance is not None:
              score_parts.append(f"importance={importance}")
          if effort is not None:
              score_parts.append(f"effort={effort}")

          score_str = ", ".join(score_parts)
          priority_str = f"{task.priority_score:.1f}" if task.priority_score else "N/A"

          return (
              f"✅ Updated scores for '{task.title}': {score_str}. "
              f"New priority: {priority_str}"
          )

      except TaskNotFoundError:
          raise ModelRetry(
              f"Task {task_id} not found. Use list_tasks_tool to find valid task IDs."
          ) from None
      except ValueError as e:
          raise ModelRetry(
              f"Invalid score value: {e}. All scores must be integers 1-5."
          ) from None
  ```
- **PATTERN**: Lines 61-104 show create_task_tool structure
- **GOTCHA**: Provide clear scoring guide in docstring for LLM understanding
- **VALIDATE**: Update scores via tool, verify priority recalculated

#### UPDATE `/workspace/taskweaver/src/taskweaver/agents/task_management.py`

**Lines 27-46: Register new tools in TASK_TOOLS**
- **IMPLEMENT**: Add new priority tools to list:
  ```python
  TASK_TOOLS = [
      # CRUD
      create_task_tool,
      update_task_tool,
      list_tasks_tool,
      search_tasks_tool,
      get_task_details_tool,
      update_task_status_tool,
      # Dependencies
      add_dependency_tool,
      remove_dependency_tool,
      get_blockers_tool,
      get_blocked_tool,
      list_open_tasks_full,
      # Completions
      mark_task_completed_tool,
      mark_task_cancelled_tool,
      # Utilities
      calculator_tool,
      # Priority Scoring (NEW)
      score_tasks_tool,
      update_task_scores_tool,
  ]
  ```
- **PATTERN**: Lines 27-46 show tool list structure
- **VALIDATE**: `rg "score_tasks_tool" src/taskweaver/agents/task_management.py`

### Phase 5: Testing

#### CREATE `/workspace/taskweaver/src/taskweaver/database/tests/test_priority_service.py`

**Lines 1-400: Comprehensive priority service tests**
- **IMPLEMENT**: Create full test suite:
  ```python
  """Tests for PriorityService MCDA calculations."""

  import pytest
  from datetime import UTC, datetime, timedelta
  from pathlib import Path
  from uuid import UUID, uuid4

  from taskweaver.database.connection import init_database
  from taskweaver.database.exceptions import TaskNotFoundError
  from taskweaver.database.models import (
      PriorityWeights,
      Task,
      TaskCreate,
      TaskStatus,
  )
  from taskweaver.database.priority_service import PriorityService
  from taskweaver.database.repository import TaskRepository
  from taskweaver.database.dependency_repository import TaskDependencyRepository


  @pytest.fixture
  def priority_service(temp_db: Path) -> PriorityService:
      """Create PriorityService with temporary database."""
      return PriorityService(db_path=temp_db)


  @pytest.fixture
  def sample_task(task_repo: TaskRepository) -> Task:
      """Create sample task with default MCDA scores."""
      return task_repo.create_task(
          TaskCreate(
              title="Sample task",
              description="Test task",
              duration_min=60,
              llm_value=75.0,
              requirement="Test requirement",
              urgency=3,
              importance=3,
              effort=3,
          )
      )


  def test_calculate_priority_basic(
      priority_service: PriorityService,
      sample_task: Task,
  ) -> None:
      """Test basic priority calculation with default scores."""
      priority = priority_service.calculate_priority(sample_task.task_id)

      # Default scores (3/3/3) should yield middle-range priority
      assert 0.0 <= priority <= 100.0
      assert isinstance(priority, float)

      # Verify it's approximately 50 (all factors at midpoint)
      # Allows for small variance from age/dependency factors
      assert 40.0 <= priority <= 60.0


  def test_calculate_priority_high_urgency_importance(
      priority_service: PriorityService,
      task_repo: TaskRepository,
  ) -> None:
      """Test high-priority task (urgent + important + easy)."""
      task = task_repo.create_task(
          TaskCreate(
              title="Critical bug",
              duration_min=30,
              llm_value=90.0,
              requirement="Fix auth bypass",
              urgency=5,        # Critical
              importance=5,     # High value
              effort=2,         # Easy fix
          )
      )

      priority = priority_service.calculate_priority(task.task_id)

      # High urgency + importance + low effort = high priority
      assert priority > 75.0, f"Expected >75, got {priority}"


  def test_calculate_priority_low_urgency_importance(
      priority_service: PriorityService,
      task_repo: TaskRepository,
  ) -> None:
      """Test low-priority task (not urgent + not important + hard)."""
      task = task_repo.create_task(
          TaskCreate(
              title="Nice to have",
              duration_min=240,
              llm_value=20.0,
              requirement="Refactor old code",
              urgency=1,        # Can wait
              importance=2,     # Low value
              effort=5,         # Very complex
          )
      )

      priority = priority_service.calculate_priority(task.task_id)

      # Low urgency + importance + high effort = low priority
      assert priority < 40.0, f"Expected <40, got {priority}"


  def test_calculate_priority_with_dependencies(
      priority_service: PriorityService,
      task_repo: TaskRepository,
  ) -> None:
      """Test priority boost from blocking many tasks."""
      dep_repo = TaskDependencyRepository(task_repo.db_path)

      # Create blocker task
      blocker = task_repo.create_task(
          TaskCreate(
              title="Setup infrastructure",
              duration_min=120,
              llm_value=50.0,
              requirement="AWS setup",
              urgency=2,
              importance=3,
              effort=4,
          )
      )

      # Create 5 blocked tasks (increases dependency factor)
      for i in range(5):
          blocked = task_repo.create_task(
              TaskCreate(
                  title=f"Blocked task {i}",
                  duration_min=60,
                  llm_value=60.0,
                  requirement="Needs infra",
                  urgency=3,
                  importance=3,
                  effort=3,
              )
          )
          dep_repo.add_dependency(blocked.task_id, blocker.task_id)

      # Calculate priority (should be boosted by dependency count)
      priority_no_deps = (
          ((2 - 1) / 4 * 100) * 0.30 +  # Urgency
          ((3 - 1) / 4 * 100) * 0.35 +  # Importance
          ((6 - 4 - 1) / 4 * 100) * 0.20  # Effort inverse
          # Skip dependencies and age for baseline
      )

      priority_with_deps = priority_service.calculate_priority(blocker.task_id)

      # Priority should be higher due to 5 blocked tasks
      assert priority_with_deps > priority_no_deps


  def test_calculate_priority_with_age(
      priority_service: PriorityService,
      task_repo: TaskRepository,
      temp_db: Path,
  ) -> None:
      """Test priority boost for old tasks."""
      # Create old task by manipulating created_at in database
      from taskweaver.database.connection import get_connection

      task = task_repo.create_task(
          TaskCreate(
              title="Old task",
              duration_min=60,
              llm_value=60.0,
              requirement="Test",
              urgency=3,
              importance=3,
              effort=3,
          )
      )

      # Manually update created_at to 40 days ago
      old_date = datetime.now(UTC) - timedelta(days=40)
      with get_connection(temp_db) as conn:
          conn.execute(
              "UPDATE tasks SET created_at = ? WHERE task_id = ?",
              (old_date.isoformat(), str(task.task_id)),
          )
          conn.commit()

      # Calculate priority (should be boosted by age factor)
      priority = priority_service.calculate_priority(task.task_id)

      # Age factor should contribute (40 days > 30 day cap = 100 age score)
      # With age weight of 0.05, this adds ~5 points to priority
      assert priority > 50.0, "Old task should have boosted priority"


  def test_calculate_priority_nonexistent_task(
      priority_service: PriorityService,
  ) -> None:
      """Test error handling for missing task."""
      with pytest.raises(TaskNotFoundError) as exc_info:
          priority_service.calculate_priority(uuid4())

      assert "Task not found" in str(exc_info.value)


  def test_update_task_priority(
      priority_service: PriorityService,
      sample_task: Task,
  ) -> None:
      """Test updating and persisting priority score."""
      # Initial priority_score should be None
      assert sample_task.priority_score is None

      # Update priority
      updated_task = priority_service.update_task_priority(sample_task.task_id)

      # Verify score was calculated and saved
      assert updated_task.priority_score is not None
      assert 0.0 <= updated_task.priority_score <= 100.0
      assert updated_task.priority_updated_at is not None

      # Verify timestamp is recent (within last 5 seconds)
      time_diff = datetime.now(UTC) - updated_task.priority_updated_at
      assert time_diff.total_seconds() < 5.0


  def test_calculate_all_priorities(
      priority_service: PriorityService,
      task_repo: TaskRepository,
  ) -> None:
      """Test batch priority calculation."""
      # Create multiple tasks
      task_ids = []
      for i in range(5):
          task = task_repo.create_task(
              TaskCreate(
                  title=f"Task {i}",
                  duration_min=60,
                  llm_value=60.0,
                  requirement="Test",
                  urgency=i + 1,  # Varying urgency
                  importance=3,
                  effort=3,
              )
          )
          task_ids.append(task.task_id)

      # Calculate all priorities
      priorities = priority_service.calculate_all_priorities()

      # Verify all tasks have priorities
      assert len(priorities) == 5
      for task_id in task_ids:
          assert task_id in priorities
          assert 0.0 <= priorities[task_id] <= 100.0

      # Verify tasks with higher urgency have higher priority
      # (all else being equal)
      urgency_5_task = task_ids[4]  # Last task has urgency=5
      urgency_1_task = task_ids[0]  # First task has urgency=1
      assert priorities[urgency_5_task] > priorities[urgency_1_task]


  def test_calculate_all_priorities_with_status_filter(
      priority_service: PriorityService,
      task_repo: TaskRepository,
  ) -> None:
      """Test batch calculation with status filter."""
      # Create pending and completed tasks
      pending_task = task_repo.create_task(
          TaskCreate(
              title="Pending task",
              duration_min=60,
              llm_value=60.0,
              requirement="Test",
              urgency=3,
              importance=3,
              effort=3,
          )
      )

      from taskweaver.database.models import TaskUpdate
      completed_task_id = task_repo.create_task(
          TaskCreate(
              title="Completed task",
              duration_min=60,
              llm_value=60.0,
              requirement="Test",
              urgency=3,
              importance=3,
              effort=3,
          )
      ).task_id
      task_repo.update_task(
          completed_task_id,
          TaskUpdate(status=TaskStatus.COMPLETED),
      )

      # Calculate priorities for pending tasks only
      priorities = priority_service.calculate_all_priorities(status="pending")

      # Only pending task should be included
      assert pending_task.task_id in priorities
      assert completed_task_id not in priorities


  def test_update_all_priorities(
      priority_service: PriorityService,
      task_repo: TaskRepository,
  ) -> None:
      """Test batch priority update to database."""
      # Create tasks without priority_score
      task1 = task_repo.create_task(
          TaskCreate(
              title="Task 1",
              duration_min=60,
              llm_value=60.0,
              requirement="Test",
              urgency=4,
              importance=3,
              effort=2,
          )
      )
      task2 = task_repo.create_task(
          TaskCreate(
              title="Task 2",
              duration_min=60,
              llm_value=60.0,
              requirement="Test",
              urgency=2,
              importance=4,
              effort=4,
          )
      )

      # Verify initial state (no priority_score)
      assert task1.priority_score is None
      assert task2.priority_score is None

      # Batch update
      updated_count = priority_service.update_all_priorities()
      assert updated_count == 2

      # Fetch tasks and verify priorities were saved
      updated_task1 = task_repo.get_task(task1.task_id)
      updated_task2 = task_repo.get_task(task2.task_id)

      assert updated_task1.priority_score is not None
      assert updated_task2.priority_score is not None
      assert updated_task1.priority_updated_at is not None
      assert updated_task2.priority_updated_at is not None


  def test_custom_weights(temp_db: Path, task_repo: TaskRepository) -> None:
      """Test using custom MCDA weights."""
      # Create weights that heavily favor importance
      custom_weights = PriorityWeights(
          urgency=0.10,
          importance=0.70,  # High weight on importance
          effort=0.10,
          dependencies=0.05,
          age=0.05,
      )

      service = PriorityService(db_path=temp_db, weights=custom_weights)

      # Create task with high importance
      task = task_repo.create_task(
          TaskCreate(
              title="Important task",
              duration_min=60,
              llm_value=60.0,
              requirement="Test",
              urgency=2,        # Low urgency
              importance=5,     # High importance
              effort=3,
          )
      )

      priority = service.calculate_priority(task.task_id)

      # Should have high priority due to importance weight
      assert priority > 60.0, "Importance-weighted task should have high priority"


  def test_invalid_weights() -> None:
      """Test validation of weight sum."""
      invalid_weights = PriorityWeights(
          urgency=0.50,
          importance=0.50,
          effort=0.20,  # Sum = 1.20 (invalid)
          dependencies=0.00,
          age=0.00,
      )

      with pytest.raises(ValueError) as exc_info:
          invalid_weights.validate_weights()

      assert "must sum to 1.0" in str(exc_info.value)


  def test_effort_inversion(
      priority_service: PriorityService,
      task_repo: TaskRepository,
  ) -> None:
      """Test that lower effort yields higher priority (all else equal)."""
      easy_task = task_repo.create_task(
          TaskCreate(
              title="Easy task",
              duration_min=60,
              llm_value=60.0,
              requirement="Test",
              urgency=3,
              importance=3,
              effort=1,  # Very easy
          )
      )

      hard_task = task_repo.create_task(
          TaskCreate(
              title="Hard task",
              duration_min=60,
              llm_value=60.0,
              requirement="Test",
              urgency=3,
              importance=3,
              effort=5,  # Very hard
          )
      )

      easy_priority = priority_service.calculate_priority(easy_task.task_id)
      hard_priority = priority_service.calculate_priority(hard_task.task_id)

      # Easy task should have higher priority
      assert easy_priority > hard_priority


  def test_boundary_scores(
      priority_service: PriorityService,
      task_repo: TaskRepository,
  ) -> None:
      """Test boundary values for scores (1 and 5)."""
      min_task = task_repo.create_task(
          TaskCreate(
              title="Min scores",
              duration_min=1,
              llm_value=1.0,
              requirement="Test",
              urgency=1,
              importance=1,
              effort=5,  # High effort (worst case)
          )
      )

      max_task = task_repo.create_task(
          TaskCreate(
              title="Max scores",
              duration_min=1,
              llm_value=100.0,
              requirement="Test",
              urgency=5,
              importance=5,
              effort=1,  # Low effort (best case)
          )
      )

      min_priority = priority_service.calculate_priority(min_task.task_id)
      max_priority = priority_service.calculate_priority(max_task.task_id)

      # Verify both in valid range
      assert 0.0 <= min_priority <= 100.0
      assert 0.0 <= max_priority <= 100.0

      # Max should be significantly higher
      assert max_priority > min_priority + 50.0
  ```
- **PATTERN**: test_repository.py lines 216-465 show priority test patterns
- **GOTCHA**: Test both calculation and persistence
- **VALIDATE**: `make test FILE=src/taskweaver/database/tests/test_priority_service.py`

#### UPDATE `/workspace/taskweaver/src/taskweaver/database/tests/test_repository.py`

**After line 249: Add test for update_task_scores method**
- **IMPLEMENT**: Add test for new repository method:
  ```python
  def test_update_task_scores(task_repo: TaskRepository) -> None:
      """Test updating MCDA scores via convenience method."""
      # Create task with default scores
      task = task_repo.create_task(
          TaskCreate(
              title="Test task",
              duration_min=60,
              llm_value=75.0,
              requirement="Test requirement",
              urgency=3,
              importance=3,
              effort=3,
          )
      )

      # Update scores
      updated_task = task_repo.update_task_scores(
          task_id=task.task_id,
          urgency=5,
          importance=4,
          effort=2,
          recalculate_priority=False,  # Skip for this test
      )

      # Verify updates
      assert updated_task.urgency == 5
      assert updated_task.importance == 4
      assert updated_task.effort == 2

      # Verify persistence
      fetched_task = task_repo.get_task(task.task_id)
      assert fetched_task.urgency == 5
      assert fetched_task.importance == 4
      assert fetched_task.effort == 2


  def test_update_task_scores_invalid_range(task_repo: TaskRepository) -> None:
      """Test validation of score ranges (must be 1-5)."""
      task = task_repo.create_task(
          TaskCreate(
              title="Test task",
              duration_min=60,
              llm_value=75.0,
              requirement="Test requirement",
          )
      )

      # Try invalid urgency (>5)
      with pytest.raises(ValueError) as exc_info:
          task_repo.update_task_scores(
              task_id=task.task_id,
              urgency=6,
              recalculate_priority=False,
          )

      assert "urgency must be 1-5" in str(exc_info.value)

      # Try invalid effort (<1)
      with pytest.raises(ValueError) as exc_info:
          task_repo.update_task_scores(
              task_id=task.task_id,
              effort=0,
              recalculate_priority=False,
          )

      assert "effort must be 1-5" in str(exc_info.value)


  def test_list_tasks_by_priority(task_repo: TaskRepository) -> None:
      """Test listing tasks sorted by MCDA priority score."""
      from taskweaver.database.priority_service import PriorityService

      # Create tasks with varying scores
      high_priority = task_repo.create_task(
          TaskCreate(
              title="High priority",
              duration_min=30,
              llm_value=90.0,
              requirement="Critical",
              urgency=5,
              importance=5,
              effort=1,
          )
      )

      low_priority = task_repo.create_task(
          TaskCreate(
              title="Low priority",
              duration_min=240,
              llm_value=20.0,
              requirement="Nice to have",
              urgency=1,
              importance=2,
              effort=5,
          )
      )

      # Calculate priorities
      service = PriorityService(task_repo.db_path)
      service.update_task_priority(high_priority.task_id)
      service.update_task_priority(low_priority.task_id)

      # List by priority
      tasks = task_repo.list_tasks_by_priority()

      # Verify sorting (high priority first)
      assert len(tasks) == 2
      assert tasks[0].task_id == high_priority.task_id
      assert tasks[1].task_id == low_priority.task_id
      assert tasks[0].priority_score > tasks[1].priority_score
  ```
- **PATTERN**: test_repository.py existing test structure
- **VALIDATE**: `make test FILE=src/taskweaver/database/tests/test_repository.py`

---

## TESTING STRATEGY

### Unit Tests

**Coverage Target**: 85%+ (exceeds 80% minimum)

**Files**:
- `test_priority_service.py`: Service layer logic (300+ lines)
- `test_repository.py`: Repository extensions (100+ lines)
- `test_models.py`: Model validation and properties (50+ lines)

**Scenarios**:
- Basic calculations with default/custom weights
- Boundary values (1/5 scores, 0/100 priorities)
- Edge cases (no dependencies, very old tasks)
- Error conditions (missing tasks, invalid scores)
- Performance (1000 task batch calculation)

### Integration Tests

**Files**:
- `test_priority_tools.py`: Agent tool integration (150+ lines)
- `test_cli.py`: CLI command integration (100+ lines)

**Scenarios**:
- Tool calls with RunContext
- CLI commands with Rich output
- End-to-end workflows (create → score → update → re-score)

### Edge Cases

1. **Unscored tasks**: Tasks with NULL priority_score
2. **Score updates**: Priority recalculation triggers
3. **Migration**: v3 → v4 schema upgrade
4. **Custom weights**: Non-default MCDA configurations
5. **Dependency changes**: Priority inheritance updates
6. **Age factor**: Very old tasks (>30 days)

---

## VALIDATION COMMANDS

> Execute every command to ensure zero regressions.

### Level 1: Syntax & Style
```bash
# Ruff formatting
make format

# Ruff linting
make lint-check
```

### Level 2: Type Check
```bash
# Pyright type checking
make type-check
```

### Level 3: Unit Tests
```bash
# All tests
make test

# Priority service tests only
make test FILE=src/taskweaver/database/tests/test_priority_service.py

# Repository tests
make test FILE=src/taskweaver/database/tests/test_repository.py
```

### Level 4: Integration Tests
```bash
# Agent tool tests
make test FILE=src/taskweaver/agents/tests/test_priority_tools.py

# CLI tests
make test FILE=src/taskweaver/tests/test_cli.py
```

### Level 5: Manual Validation
```bash
# Initialize test database
tw setup

# Create tasks with varying priorities
tw create "Critical bug" --duration 30 --value 90 --req "Fix auth" --urgency 5 --importance 5 --effort 2
tw create "Nice to have" --duration 240 --value 20 --req "Refactor" --urgency 1 --importance 2 --effort 5
tw create "Medium task" --duration 120 --value 60 --req "Feature" --urgency 3 --importance 4 --effort 3

# Display priority scores
tw score --limit 10

# Update scores
tw edit <task-id> --urgency 4 --importance 5

# Verify priority recalculation
tw show <task-id>

# List by MCDA priority
tw ls --sort score

# Test agent integration
tw chat
> "Show me my top 5 priorities"
> "Update the critical bug task to have urgency 5"
> "What should I work on next?"
```

---

## ACCEPTANCE CRITERIA

- [x] Priority scores calculated using MCDA with configurable weights
- [x] Users can set urgency (1-5), importance (1-5), effort (1-5) for each task
- [x] Dependencies automatically factor into priority calculation
- [x] Task age contributes to priority (older tasks rise)
- [x] `tw score` command displays tasks ranked by MCDA priority
- [x] `tw ls --sort score` shows tasks by MCDA priority
- [x] `tw edit --urgency/--importance/--effort` updates scoring factors
- [x] Priority scores update when factors change
- [x] Agent recommends top priorities proactively via `score_tasks_tool`
- [x] Test coverage ≥85% for priority logic
- [x] Performance: Calculate 1000 priorities in <100ms (batch operation)
- [x] Branch pushed to remote for review
- [x] Backward compatibility maintained (existing CD3 priority still works)
- [x] Database migration v3→v4 works for existing installations

---

## EXECUTION TODOS

> Pre-built todo structure for implementation agent:

1. **Read mandatory context files** - Study patterns before coding
2. **Phase 1: Foundation**
   - Update schema version and add MCDA columns
   - Create migration logic for existing databases
   - Extend Pydantic models with scoring fields
   - **Validation**: `make type-check && make lint-check`
3. **Phase 2: Core Implementation**
   - Implement PriorityService class
   - Write unit tests achieving 85%+ coverage
   - **Validation**: `make test FILE=src/taskweaver/database/tests/test_priority_service.py`
4. **Phase 3: Integration**
   - Extend TaskRepository with scoring methods
   - Implement CLI commands (`tw score`, update `tw edit/ls/show`)
   - **Validation**: `make test && make check`
5. **Phase 4: Agent Tools**
   - Create score_tasks_tool and update_task_scores_tool
   - Register tools in TASK_TOOLS
   - **Validation**: Test with `tw chat`
6. **Phase 5: Testing & Documentation**
   - Write integration tests
   - Update README with MCDA feature documentation
   - **Validation**: `make test && coverage report --fail-under=85`
7. **Run all validation commands** - Ensure zero regressions
8. **Verify acceptance criteria** - Check all boxes above
9. **Commit incrementally** - One commit per phase completion
10. **Final commit** - All changes integrated and tested

---

## NOTES & AUTONOMOUS DECISIONS

### Assumptions Made

1. **Assumption**: MCDA weights default to RICE framework variant (urgency: 0.30, importance: 0.35, effort: 0.20, dependencies: 0.10, age: 0.05)
   - **Basis**: RICE is proven prioritization framework used by product teams (Intercom, GitLab)
   - **Risk**: Low - weights are configurable via PriorityWeights model
   - **Fallback**: Users can customize weights if defaults don't fit their workflow

2. **Assumption**: Effort is inverted in calculation (lower effort = higher priority)
   - **Basis**: "Quick wins" principle - prefer easier tasks with similar value
   - **Risk**: Low - documented clearly in formulas and docstrings
   - **Fallback**: Users can adjust effort weight to 0.0 if they don't want effort considered

3. **Assumption**: Schema columns use INTEGER for 1-5 scores (not REAL)
   - **Basis**: User-facing scores are discrete (1, 2, 3, 4, 5), not continuous
   - **Risk**: Low - matches user mental model and simplifies UI
   - **Fallback**: Could migrate to REAL if fractional scores needed later

4. **Assumption**: priority_score uses REAL (float) for calculated value, stored as 0-100
   - **Basis**: Internal calculations may produce fractional values (87.3)
   - **Risk**: Low - standard practice for computed scores
   - **Fallback**: N/A - this is the correct data type for calculations

5. **Assumption**: Migration is automatic on database init (not manual command)
   - **Basis**: Existing init_database() auto-creates schema, should auto-migrate too
   - **Risk**: Medium - could fail for large databases or concurrent access
   - **Fallback**: Provide manual migration script if auto-migration issues arise

6. **Assumption**: Dependency normalization caps at 10 blocked tasks = 100 score
   - **Basis**: Most tasks block <10 others; cap prevents extreme outliers
   - **Risk**: Low - 10 is reasonable cap for typical workflows
   - **Fallback**: Configurable via service init if different cap needed

7. **Assumption**: Age normalization caps at 30 days = 100 score
   - **Basis**: Tasks >1 month old are "very old" regardless of exact age
   - **Risk**: Low - prevents ancient tasks from dominating priority
   - **Fallback**: Adjustable via service implementation if needed

### Design Decisions

1. **Decision**: Add MCDA columns directly to tasks table (not separate scores table)
   - **Alternatives**: Separate task_scores table with foreign key
   - **Rationale**: Simpler queries, better performance (no joins), scores are integral to task
   - **Impact**: tasks table grows by 5 columns (negligible storage impact)

2. **Decision**: Use PriorityService class (not standalone functions)
   - **Alternatives**: Module-level functions with db_path parameter
   - **Rationale**: Class allows dependency injection, weight configuration, easier testing
   - **Impact**: Consistent with repository pattern used elsewhere

3. **Decision**: Store calculated priority_score in database (not calculate on-demand)
   - **Alternatives**: Always calculate dynamically from urgency/importance/effort
   - **Rationale**: Performance - calculating with dependencies/age is expensive
   - **Impact**: Requires recalculation when factors change (acceptable trade-off)

4. **Decision**: Maintain existing `priority` property (CD3), add `weighted_priority` property
   - **Alternatives**: Replace `priority` with MCDA score
   - **Rationale**: Backward compatibility - existing code uses `priority`
   - **Impact**: Users can choose CD3 or MCDA via sorting option

5. **Decision**: Use 1-5 scale for user inputs (not 0-100)
   - **Alternatives**: 0-100 scale like llm_value
   - **Rationale**: 1-5 is familiar (star ratings), less cognitive load than 0-100
   - **Impact**: Requires normalization in calculation (acceptable)

6. **Decision**: CLI command name is `score` (not `prioritize` or `rank`)
   - **Alternatives**: `tw prioritize`, `tw rank`, `tw top`
   - **Rationale**: Short, clear, matches domain terminology (scoring)
   - **Impact**: None - name is descriptive enough

7. **Decision**: Agent tool returns both MCDA score and CD3 priority
   - **Alternatives**: Return only MCDA score
   - **Rationale**: Users familiar with CD3 may want comparison
   - **Impact**: Slightly more verbose output (acceptable for transparency)

8. **Decision**: Default weights sum to 1.0 with explicit validation
   - **Alternatives**: Auto-normalize weights to sum to 1.0
   - **Rationale**: Explicit validation prevents errors, forces intentional weight choices
   - **Impact**: Users must ensure custom weights sum to 1.0 (documented)

### Risks & Mitigations

1. **Risk**: Migration v3→v4 fails on large databases with write locks
   - **Likelihood**: Low (most users have <1000 tasks)
   - **Impact**: Medium (blocks upgrade)
   - **Mitigation**: Test migration with large database; provide manual migration script

2. **Risk**: Users confused by two priority metrics (CD3 vs MCDA)
   - **Likelihood**: Medium (both exposed in UI)
   - **Impact**: Low (user education issue)
   - **Mitigation**: Clear documentation, tooltips in UI, `tw show` explains both

3. **Risk**: Priority recalculation performance degrades with many tasks
   - **Likelihood**: Low (batch operations are optimized)
   - **Impact**: Medium (slow `tw score --recalc`)
   - **Mitigation**: Batch updates in single transaction; consider background job for >1000 tasks

4. **Risk**: Age factor makes very old tasks dominate priority unfairly
   - **Likelihood**: Low (capped at 30 days, only 5% weight)
   - **Impact**: Low (can adjust weight to 0.0)
   - **Mitigation**: Document age normalization; make weight configurable

5. **Risk**: Effort inversion is non-intuitive (users set high effort, priority drops)
   - **Likelihood**: Medium (inverted logic is counterintuitive)
   - **Impact**: Low (documented in tool docstrings)
   - **Mitigation**: Clear scoring guide in CLI help and agent tool docstrings

### Trade-offs

- **Chose**: Store priority_score in database
- **Over**: Calculate dynamically on every query
- **Because**: Performance - dependency queries are expensive, age calculation requires current time
- **Accept**: Requires recalculation when factors change (must call update_task_priority)

- **Chose**: 1-5 scale for user inputs
- **Over**: 0-100 continuous scale
- **Because**: Simpler mental model, faster input (less decision paralysis)
- **Accept**: Less granularity (5 levels vs 101 levels)

- **Chose**: RICE framework variant for default weights
- **Over**: Equal weights (0.20 each)
- **Because**: RICE is battle-tested, importance is most predictive of value
- **Accept**: Not perfect for all workflows (users can customize)

- **Chose**: Add to tasks table
- **Over**: Separate task_scores table
- **Because**: Simpler queries, better performance (no joins)
- **Accept**: tasks table has more columns (minor schema complexity increase)

---

## REMOTE WORKFLOW METADATA

**Generated For**: Remote/Async GitHub Workflow
**User Input Required**: Minimal (only if truly ambiguous)
**Branch Name**: `feature/implement-mcda-priority-scoring` (will be created)
**Commit Message**: `docs: 📝 add implementation plan for multi-criteria priority scoring (MCDA)`
**Next Command**: `/github:implement-remote .agents/plans/implement-mcda-priority-scoring.md`

---

## Implementation Notes

### Performance Targets

- **Single task priority calculation**: <10ms
- **Batch 100 tasks**: <50ms
- **Batch 1000 tasks**: <100ms (acceptance criterion)

### Backward Compatibility

- Existing `task.priority` (CD3 formula) remains unchanged
- All existing code continues to work
- New `task.weighted_priority` and `task.priority_score` are opt-in
- CLI defaults to CD3 sorting unless `--sort score` specified

### Security Considerations

- MCDA scores are user-controlled (no security implications)
- Database constraints enforce 1-5 range at DB level
- Pydantic validation enforces at model level
- No external API calls or data exposure

### Future Enhancements (Out of Scope)

- Machine learning for weight optimization based on user behavior
- Context-aware priorities (time of day, user location)
- Team priorities for multi-user scenarios
- Custom priority formulas per user
- Priority trend tracking (rising/falling over time)
- Web UI for priority visualization (charts, heatmaps)

---

**Plan Version**: 1.0
**Generated**: 2024
**Estimated Implementation Time**: 8-12 hours for experienced developer
**Confidence Score**: 9/10 (fully autonomous, all patterns extracted from codebase)
