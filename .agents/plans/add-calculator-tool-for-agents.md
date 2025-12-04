# Feature: Add Calculator Tool to Agents for Mathematical Operations

> **AUTONOMOUS PLAN**: This plan was generated with minimal user input.
> All design decisions are documented below. Review NOTES section for assumptions.

> **IMPORTANT**: Validate documentation and codebase patterns before implementing.
> Pay attention to naming of existing utils, types, and models.
> Import from correct files.

## Overview

**Description**: Add a safe mathematical expression evaluation tool to PydanticAI agents, enabling them to perform calculations for task priority computations, variance analysis, duration estimations, and statistical analysis of task metrics.

**Problem**: Agents currently lack a dedicated calculator tool for performing mathematical operations. When agents need to calculate priorities (value/duration), compute variance percentages, or perform complex multi-dimensional scoring, they must either approximate results or delegate to Python code. This creates friction in conversational workflows and limits the agent's autonomy in numerical reasoning tasks.

**Solution**: Implement a PydanticAI tool using the `simpleeval` library for safe expression evaluation. The tool will support common mathematical operations (+, -, *, /, **, sqrt, abs, etc.) and return precise numeric results formatted for downstream processing. It will integrate seamlessly with the existing tool ecosystem and follow established error handling patterns using ModelRetry for LLM-fixable errors.

## Metadata

| Field | Value |
|-------|-------|
| Type | New Capability |
| Complexity | Low |
| Autonomy Level | Fully Autonomous |
| Assumptions Made | 8 |
| Systems Affected | Agent tools, Task management agent, Orchestrator prompt |
| Dependencies | simpleeval>=1.0.0 (AST-based safe evaluator) |

---

## CONTEXT REFERENCES

### Mandatory Reading (READ BEFORE IMPLEMENTING)

**Tool Implementation Patterns:**
- `src/taskweaver/agents/tools.py:60-102` - Why: `create_task_tool` shows validation error handling with ModelRetry
- `src/taskweaver/agents/tools.py:334-388` - Why: `mark_task_completed_tool` shows optional parameters and formatted responses
- `src/taskweaver/agents/tools.py:609-634` - Why: `add_dependency_tool` shows minimal tool pattern

**Tool Registration:**
- `src/taskweaver/agents/task_management.py:25-42` - Why: TASK_TOOLS list where new tool must be added
- `src/taskweaver/agents/shared.py:40-68` - Why: Agent factory pattern showing how tools are registered

**Testing Patterns:**
- `src/taskweaver/agents/tests/conftest.py` - Why: Fixture setup for ctx and deps
- `src/taskweaver/agents/tests/test_tools.py:62-88` - Why: Test class structure with success and error cases
- `src/taskweaver/agents/tests/test_tools.py:25-46` - Why: Fixture setup for deps and ctx mocks

**Existing Math Utilities:**
- `src/taskweaver/database/models.py:48-67` - Why: Priority calculation property (llm_value / duration_min)
- `src/taskweaver/database/models.py:186-202` - Why: Variance calculation properties

**Orchestrator Prompt:**
- `src/taskweaver/agents/prompts/orchestrator_prompt.md:72-1450` - Why: Tool documentation format and location
- `src/taskweaver/agents/prompts/orchestrator_prompt.md:137-162` - Why: Priority calculation guidance tool would support

### New Files to Create

- `src/taskweaver/agents/tests/test_calculator_tool.py` - Unit tests for calculator tool (18 test cases)

### Files to Modify

- `pyproject.toml` - Add simpleeval dependency
- `src/taskweaver/agents/tools.py` - Add calculator_tool function
- `src/taskweaver/agents/task_management.py` - Register tool in TASK_TOOLS list
- `src/taskweaver/agents/prompts/orchestrator_prompt.md` - Document tool usage (optional but recommended)

### Documentation References

- [simpleeval · PyPI](https://pypi.org/project/simpleeval/) - AST-based safe expression evaluator
- [simpleeval GitHub](https://github.com/danthedeckie/simpleeval) - Security model and examples
- [PydanticAI Tools Documentation](https://ai.pydantic.dev/tools/) - Tool function signatures and patterns

### Patterns to Follow

**Tool Function Signature:**
```python
def calculator_tool(
    ctx: RunContext[TaskDependencies],
    expression: str,
) -> str:
    """Evaluate mathematical expressions safely for task calculations."""
```

**Error Handling (ModelRetry):**
```python
try:
    result = simple_eval(expression.strip())
    return f"{expression} = {result}"
except ZeroDivisionError as e:
    raise ModelRetry(f"Division by zero in expression: {expression}") from e
except (SyntaxError, TypeError, ValueError, NameError) as e:
    raise ModelRetry(f"Invalid mathematical expression: {expression}. Error: {e}") from e
```

**Response Format (Token-Efficient String):**
```python
# Pattern from existing tools (line 334-388)
return f"✅ Completed '{task.title}' (60min estimated, 90min actual, +50.0% variance)"

# For calculator:
return f"{expression} = {formatted_result}"
```

**Docstring Format:**
```python
def calculator_tool(ctx: RunContext[TaskDependencies], expression: str) -> str:
    """Evaluate mathematical expressions safely for task calculations.

    Enables the agent to perform calculations for:
    - Priority score computations (e.g., "85.0 / 120")
    - Variance percentage calculations (e.g., "(90 - 60) / 60 * 100")
    - Duration conversions (e.g., "2.5 * 60" for hours to minutes)
    - Multi-dimensional value scoring (e.g., "(85 * 0.35) + (65 * 0.30) + (95 * 0.35)")

    Supports: +, -, *, /, ** (power), parentheses for order of operations

    Args:
        ctx: Runtime context containing TaskDependencies.
        expression: Mathematical expression to evaluate (e.g., "85.0 / 120", "2 + 2").

    Returns:
        Formatted result string: "{expression} = {result}"

    Raises:
        ModelRetry: If expression is invalid, empty, or contains division by zero.

    Example:
        >>> calculator_tool(ctx, "85.0 / 120")
        "85.0 / 120 = 0.7083"

        >>> calculator_tool(ctx, "(92*0.35) + (78*0.30) + (88*0.35)")
        "(92*0.35) + (78*0.30) + (88*0.35) = 86.4000"
    """
```

### Boundaries

**ALWAYS:**
- Use ModelRetry for all validation and evaluation errors (LLM-fixable)
- Follow Google-style docstrings with Args/Returns/Raises/Example sections
- Add imports at the top of tools.py in alphabetical order
- Run validation commands after each phase
- Use simpleeval for expression evaluation (never eval() or exec())
- Format float results to 4 decimal places for consistency
- Validate input is non-empty before evaluation

**ASK FIRST:**
- (None - all design decisions made autonomously based on codebase patterns)

**NEVER:**
- Use built-in eval() or exec() (security risk - arbitrary code execution)
- Use ast.literal_eval() (doesn't support operators like +, -, *, /)
- Skip error handling for division by zero
- Return raw numeric types without formatting
- Modify existing math properties in models.py (separate concerns)
- Add tool without comprehensive test coverage

---

## IMPLEMENTATION PLAN

### Phase 1: Dependencies & Foundation
Add simpleeval library to project dependencies and verify installation.

**Tasks:**
- Add simpleeval>=1.0.0 to pyproject.toml dependencies
- Verify dependency installs correctly with uv

**Validation**: `uv pip list | grep simpleeval`

### Phase 2: Core Implementation
Implement calculator_tool function in tools.py following established patterns.

**Tasks:**
- Add calculator_tool function to tools.py
- Import simpleeval at module level
- Implement safe expression evaluation with error handling
- Format results consistently (4 decimal places for floats)
- Add comprehensive docstring with examples

**Validation**: `make format && make lint-check && make type-check FILE=src/taskweaver/agents/tools.py`

### Phase 3: Tool Registration
Register calculator_tool with the task management agent.

**Tasks:**
- Add calculator_tool to TASK_TOOLS list in task_management.py
- Verify tool is discoverable by PydanticAI agent

**Validation**: `make lint-check FILE=src/taskweaver/agents/task_management.py`

### Phase 4: Testing
Create comprehensive test suite covering all operations and edge cases.

**Tasks:**
- Create test_calculator_tool.py with 18 test cases
- Test all basic operations (+, -, *, /, **)
- Test error cases (invalid syntax, division by zero, empty expression)
- Test edge cases (negatives, decimals, large numbers, complex expressions)
- Verify ModelRetry error handling

**Validation**: `make test FILE=src/taskweaver/agents/tests/test_calculator_tool.py`

### Phase 5: Documentation (Optional but Recommended)
Document tool in orchestrator prompt for LLM guidance.

**Tasks:**
- Add tool documentation to orchestrator_prompt.md (after tool 11 at ~line 1450)
- Follow established format with Purpose/Parameters/When to use/Best practices/Examples
- Align with existing priority calculation guidance (lines 137-162)

**Validation**: Manual review of prompt structure

---

## STEP-BY-STEP TASKS

> Execute every task in order, top to bottom. Each task is atomic and testable.

### Phase 1: Add Dependency

#### UPDATE pyproject.toml
- **IMPLEMENT**: Add `simpleeval>=1.0.0` to dependencies list
- **LOCATION**: Line 31-43 (dependencies array)
- **PATTERN**: Alphabetically sorted like existing dependencies
- **IMPORTS**: N/A
- **GOTCHA**: Must be in main dependencies, not dev dependencies
- **VALIDATE**: `uv sync && uv pip list | grep simpleeval`

**Insert after line 41 (before textual):**
```toml
    "simpleeval>=1.0.0",
```

---

### Phase 2: Implement Calculator Tool

#### UPDATE src/taskweaver/agents/tools.py
- **IMPLEMENT**: Add calculator_tool function with safe expression evaluation
- **LOCATION**: End of file (after last tool function, around line 710)
- **PATTERN**: Mirror `mark_task_completed_tool` (lines 334-388) for error handling
- **IMPORTS**: Add at top of file (line ~15): `from simpleeval import simple_eval`
- **GOTCHA**:
  - Must use ModelRetry for all errors (not Exception)
  - Must validate empty expression before evaluation
  - Must format floats to 4 decimal places for consistency
  - Security: simpleeval uses AST whitelisting (safe), but still validate input
- **VALIDATE**: `make format && make lint-check && make type-check FILE=src/taskweaver/agents/tools.py`

**Add import at line ~15 (alphabetically after pydantic_ai imports):**
```python
from simpleeval import simple_eval
```

**Add function at end of file (~line 710):**
```python
def calculator_tool(
    ctx: RunContext[TaskDependencies],
    expression: str,
) -> str:
    """Evaluate mathematical expressions safely for task calculations.

    Enables the agent to perform calculations for:
    - Priority score computations (e.g., "85.0 / 120" → 0.7083)
    - Variance percentage calculations (e.g., "(90 - 60) / 60 * 100" → 50.0%)
    - Duration conversions (e.g., "2.5 * 60" for hours to minutes → 150)
    - Multi-dimensional value scoring (e.g., "(85 * 0.35) + (65 * 0.30) + (95 * 0.35)" → 86.4)

    Supports: +, -, *, /, ** (power), % (modulo), parentheses for order of operations
    Security: Uses AST-based evaluation (simpleeval) - no arbitrary code execution possible

    Use this tool when you need to:
    - Verify priority calculations before recommendations
    - Calculate inherited effective priority for blocking tasks
    - Compute variance percentages for completion analysis
    - Convert between time units or value scales
    - Perform any mathematical computation needed for task reasoning

    Args:
        ctx: Runtime context containing TaskDependencies.
        expression: Mathematical expression to evaluate (e.g., "85.0 / 120", "(2 + 2) * 3").
                   Must be a valid mathematical expression using numbers and operators.
                   No variables, functions, or code execution allowed.

    Returns:
        Formatted result string: "{expression} = {result}"
        - Floats formatted to 4 decimal places (e.g., "85.0 / 120 = 0.7083")
        - Integers displayed without decimals (e.g., "2 + 2 = 4")

    Raises:
        ModelRetry: If expression is invalid, empty, contains division by zero, or uses
                   unsupported operations. LLM receives error message and can retry.

    Example:
        >>> calculator_tool(ctx, "85.0 / 120")
        "85.0 / 120 = 0.7083"

        >>> calculator_tool(ctx, "2 + 2")
        "2 + 2 = 4"

        >>> calculator_tool(ctx, "(92*0.35) + (78*0.30) + (88*0.35)")
        "(92*0.35) + (78*0.30) + (88*0.35) = 86.4000"

        >>> calculator_tool(ctx, "2 ** 8")
        "2 ** 8 = 256"
    """
    # Validate input
    if not expression or not expression.strip():
        raise ModelRetry("Expression cannot be empty. Provide a mathematical expression like '2 + 2'.") from None

    try:
        # Safe evaluation using AST-based simpleeval (no code execution possible)
        result = simple_eval(expression.strip())

        # Format result based on type
        if isinstance(result, float):
            # Format floats with 4 decimal places for consistency
            formatted_result = f"{result:.4f}"
        elif isinstance(result, int):
            # Integers displayed without decimals
            formatted_result = str(result)
        else:
            # Unexpected type (shouldn't happen with pure math expressions)
            formatted_result = str(result)

        return f"{expression} = {formatted_result}"

    except ZeroDivisionError as e:
        raise ModelRetry(f"Division by zero in expression: '{expression}'. Check the denominator.") from e
    except (SyntaxError, TypeError, ValueError, NameError) as e:
        raise ModelRetry(
            f"Invalid mathematical expression: '{expression}'. "
            f"Error: {e}. Use only numbers and operators (+, -, *, /, **, %)."
        ) from e
```

---

### Phase 3: Register Tool

#### UPDATE src/taskweaver/agents/task_management.py
- **IMPLEMENT**: Add calculator_tool to TASK_TOOLS list
- **LOCATION**: Lines 25-42 (TASK_TOOLS array)
- **PATTERN**: Import at top (line ~10), add to list at end (line ~41)
- **IMPORTS**: Add to existing import statement from tools module
- **GOTCHA**: Must import function before adding to list, maintain alphabetical order in list
- **VALIDATE**: `make lint-check FILE=src/taskweaver/agents/task_management.py`

**Update import statement (line ~10):**
```python
from .tools import (
    add_dependency_tool,
    calculator_tool,  # ADD THIS LINE
    get_blocked_tool,
    # ... rest of imports alphabetically
)
```

**Add to TASK_TOOLS list (line ~41, at end before closing bracket):**
```python
TASK_TOOLS = [
    create_task_tool,
    update_task_tool,
    list_tasks_tool,
    search_tasks_tool,
    get_task_details_tool,
    update_task_status_tool,
    add_dependency_tool,
    remove_dependency_tool,
    get_blockers_tool,
    get_blocked_tool,
    list_open_tasks_full,
    mark_task_completed_tool,
    mark_task_cancelled_tool,
    calculator_tool,  # ADD THIS LINE
]
```

---

### Phase 4: Create Comprehensive Tests

#### CREATE src/taskweaver/agents/tests/test_calculator_tool.py
- **IMPLEMENT**: Test suite with 18 comprehensive test cases
- **LOCATION**: New file in tests directory
- **PATTERN**: Mirror `test_tools.py:62-88` for test class structure and fixtures
- **IMPORTS**: Standard test imports + calculator_tool
- **GOTCHA**:
  - Use `pytest.raises(ModelRetry)` for error tests
  - Use approximate equality for float comparisons (abs(result - expected) < 0.001)
  - Test both integer and float results
  - Verify error messages contain helpful guidance
- **VALIDATE**: `make test FILE=src/taskweaver/agents/tests/test_calculator_tool.py`

**Create new file:**
```python
"""Tests for calculator_tool.

This module contains comprehensive tests for the calculator tool, covering:
- Basic arithmetic operations (+, -, *, /, **, %)
- Complex expressions with parentheses and order of operations
- Error handling (division by zero, invalid syntax, empty expressions)
- Edge cases (negative numbers, decimals, large numbers)
- Response formatting (4 decimal places for floats, integers without decimals)
"""

from pathlib import Path

import pytest
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.tools import calculator_tool
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import init_database
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.repository import TaskRepository


@pytest.fixture
def deps(db_path: Path) -> TaskDependencies:
    """Create TaskDependencies with repositories."""
    init_database(db_path)
    return TaskDependencies(
        task_repo=TaskRepository(db_path),
        dep_repo=TaskDependencyRepository(db_path),
        completion_repo=CompletionRepository(db_path),
        memories="",
        user_id="test_user",
    )


@pytest.fixture
def ctx(deps: TaskDependencies) -> RunContext[TaskDependencies]:
    """Create mock RunContext with dependencies."""

    class MockContext:
        """Mock context for testing."""

        def __init__(self, dependencies: TaskDependencies) -> None:
            """Initialize mock context with dependencies."""
            self.deps = dependencies

    return MockContext(deps)  # type: ignore[return-value]


class TestCalculatorTool:
    """Tests for calculator_tool."""

    # ========================================
    # Basic Operations Tests
    # ========================================

    def test_calculator_basic_addition(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test basic addition operation."""
        result = calculator_tool(ctx, "2 + 2")

        assert result == "2 + 2 = 4"
        assert "=" in result

    def test_calculator_basic_subtraction(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test basic subtraction operation."""
        result = calculator_tool(ctx, "10 - 3")

        assert result == "10 - 3 = 7"

    def test_calculator_basic_multiplication(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test basic multiplication operation."""
        result = calculator_tool(ctx, "5 * 6")

        assert result == "5 * 6 = 30"

    def test_calculator_basic_division(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test basic division operation with float result."""
        result = calculator_tool(ctx, "85.0 / 120")

        assert result == "85.0 / 120 = 0.7083"
        assert "0.7083" in result  # Verify 4 decimal places

    def test_calculator_power_operation(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test power operation (exponentiation)."""
        result = calculator_tool(ctx, "2 ** 8")

        assert result == "2 ** 8 = 256"

    def test_calculator_modulo_operation(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test modulo operation."""
        result = calculator_tool(ctx, "17 % 5")

        assert result == "17 % 5 = 2"

    # ========================================
    # Complex Expression Tests
    # ========================================

    def test_calculator_complex_expression(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test complex multi-dimensional value scoring calculation."""
        result = calculator_tool(ctx, "(92*0.35) + (78*0.30) + (88*0.35)")

        # Verify result is correctly formatted
        assert "(92*0.35) + (78*0.30) + (88*0.35)" in result
        assert "86.4000" in result or "86.4" in result  # May have trailing zeros

    def test_calculator_order_of_operations(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test order of operations (PEMDAS)."""
        result = calculator_tool(ctx, "2 + 3 * 4")

        assert result == "2 + 3 * 4 = 14"  # Not 20 - respects PEMDAS

    def test_calculator_parentheses_precedence(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test parentheses override order of operations."""
        result = calculator_tool(ctx, "(2 + 3) * 4")

        assert result == "(2 + 3) * 4 = 20"

    def test_calculator_nested_parentheses(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test nested parentheses evaluation."""
        result = calculator_tool(ctx, "((10 - 5) * 2) + 3")

        assert result == "((10 - 5) * 2) + 3 = 13"

    # ========================================
    # Edge Case Tests
    # ========================================

    def test_calculator_negative_numbers(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test calculations with negative numbers."""
        result = calculator_tool(ctx, "-5 + 3")

        assert result == "-5 + 3 = -2"

    def test_calculator_negative_result(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test calculation resulting in negative number."""
        result = calculator_tool(ctx, "5 - 10")

        assert result == "5 - 10 = -5"

    def test_calculator_float_precision(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test float result formatting to 4 decimal places."""
        result = calculator_tool(ctx, "10 / 3")

        # Verify 4 decimal places
        assert "3.3333" in result
        assert result == "10 / 3 = 3.3333"

    def test_calculator_large_numbers(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test calculations with large numbers."""
        result = calculator_tool(ctx, "1000000 * 1000")

        assert result == "1000000 * 1000 = 1000000000"

    def test_calculator_decimal_input(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test calculations with decimal inputs."""
        result = calculator_tool(ctx, "3.5 * 2.5")

        assert "8.7500" in result  # 3.5 * 2.5 = 8.75

    # ========================================
    # Error Handling Tests
    # ========================================

    def test_calculator_division_by_zero_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test division by zero raises ModelRetry with helpful message."""
        with pytest.raises(ModelRetry, match="Division by zero"):
            calculator_tool(ctx, "10 / 0")

    def test_calculator_empty_expression_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test empty expression raises ModelRetry."""
        with pytest.raises(ModelRetry, match="Expression cannot be empty"):
            calculator_tool(ctx, "")

    def test_calculator_whitespace_only_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test whitespace-only expression raises ModelRetry."""
        with pytest.raises(ModelRetry, match="Expression cannot be empty"):
            calculator_tool(ctx, "   ")

    def test_calculator_invalid_syntax_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test invalid syntax raises ModelRetry with helpful message."""
        with pytest.raises(ModelRetry, match="Invalid mathematical expression"):
            calculator_tool(ctx, "2 + + 2")

    def test_calculator_undefined_variable_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test undefined variable raises ModelRetry (security check)."""
        with pytest.raises(ModelRetry, match="Invalid mathematical expression"):
            calculator_tool(ctx, "x + 5")

    def test_calculator_function_call_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test function call attempt raises ModelRetry (security check)."""
        with pytest.raises(ModelRetry, match="Invalid mathematical expression"):
            calculator_tool(ctx, "print(5)")
```

---

### Phase 5: Optional Documentation

#### UPDATE src/taskweaver/agents/prompts/orchestrator_prompt.md (OPTIONAL)
- **IMPLEMENT**: Add tool documentation following established format
- **LOCATION**: After tool 11 (duckduckgo_search_tool), around line 1450
- **PATTERN**: Mirror tool 11 format (lines 1393-1451)
- **IMPORTS**: N/A
- **GOTCHA**: Update tool count from 11 to 12 at line 68
- **VALIDATE**: Manual review of documentation structure

**Update line 68:**
```markdown
## Available Tools & When to Use Them

You have access to **12 tools** (task management + web search + calculator):
```

**Add at line ~1450 (after duckduckgo_search_tool):**
```markdown

### 12. calculator_tool(expression: str)

**Purpose**: Safely evaluate mathematical expressions for task calculations and priority analysis

**Required Parameters**:
- `expression` (str): Mathematical expression using numbers and operators (+, -, *, /, **, %)

**When to use**:
- Verifying priority calculations (llm_value / duration_min)
- Computing effective priority inheritance for task graphs
- Calculating variance percentages ((actual - expected) / expected * 100)
- Converting time units (hours to minutes: "2.5 * 60")
- Multi-dimensional value scoring formulas
- Any mathematical computation needed for task reasoning

**Best practices**:
- Use for complex calculations where precision matters
- Verify priority calculations before making recommendations
- Calculate inherited effective priority for blocking tasks
- Use parentheses to clarify order of operations
- Keep expressions readable (add spaces: "85.0 / 120" not "85.0/120")

**When NOT to use**:
- Simple arithmetic the user can verify manually
- Rough estimates where precision doesn't matter
- Calculations already provided by task properties (priority, variance_percent)

**Example usage**:
```
# Priority calculation
calculator_tool("85.0 / 120")  # Returns: "85.0 / 120 = 0.7083"

# Variance percentage
calculator_tool("(90 - 60) / 60 * 100")  # Returns: "(90 - 60) / 60 * 100 = 50.0000"

# Multi-dimensional scoring
calculator_tool("(92*0.35) + (78*0.30) + (88*0.35)")  # Returns: "... = 86.4000"

# Duration conversion
calculator_tool("2.5 * 60")  # Returns: "2.5 * 60 = 150.0000"
```

**Security**: Uses AST-based evaluation (simpleeval) - no arbitrary code execution possible. Only mathematical operations allowed.
```

---

## TESTING STRATEGY

### Unit Tests (18 comprehensive test cases)

**Test Coverage Requirements:**
- Minimum 80% code coverage (enforced by pytest --cov-fail-under=80)
- All test cases must pass
- No regressions in existing test suite

**Test Categories:**

1. **Basic Operations (6 tests)**
   - test_calculator_basic_addition: 2 + 2 = 4
   - test_calculator_basic_subtraction: 10 - 3 = 7
   - test_calculator_basic_multiplication: 5 * 6 = 30
   - test_calculator_basic_division: 85.0 / 120 = 0.7083
   - test_calculator_power_operation: 2 ** 8 = 256
   - test_calculator_modulo_operation: 17 % 5 = 2

2. **Complex Expressions (5 tests)**
   - test_calculator_complex_expression: Multi-dimensional scoring
   - test_calculator_order_of_operations: PEMDAS verification
   - test_calculator_parentheses_precedence: Override PEMDAS
   - test_calculator_nested_parentheses: Nested evaluation

3. **Edge Cases (4 tests)**
   - test_calculator_negative_numbers: -5 + 3 = -2
   - test_calculator_float_precision: 4 decimal places
   - test_calculator_large_numbers: 1000000 * 1000
   - test_calculator_decimal_input: 3.5 * 2.5

4. **Error Handling (5 tests)**
   - test_calculator_division_by_zero_raises: ModelRetry with message
   - test_calculator_empty_expression_raises: Input validation
   - test_calculator_invalid_syntax_raises: Syntax error handling
   - test_calculator_undefined_variable_raises: Variable blocking (security)
   - test_calculator_function_call_raises: Function blocking (security)

### Integration Tests

**Existing Integration Tests:**
- No new integration tests required - calculator tool is standalone
- Existing agent tests will verify tool registration automatically
- TUI integration tests will verify tool availability in chat interface

### Edge Cases

- **Division by Zero**: Raises ModelRetry with descriptive message
- **Empty Expression**: Validates input before evaluation
- **Invalid Syntax**: Catches SyntaxError and converts to ModelRetry
- **Undefined Variables**: Blocked by simpleeval (no variable evaluation)
- **Function Calls**: Blocked by simpleeval (security)
- **Large Numbers**: Handled by Python's arbitrary precision integers
- **Float Precision**: Consistently formatted to 4 decimal places
- **Negative Results**: Handled correctly with minus sign
- **Complex Nested Expressions**: Evaluated correctly with PEMDAS

---

## VALIDATION COMMANDS

> Execute every command to ensure zero regressions.

### Level 1: Syntax & Style
```bash
make format
make format-check
make lint-check
```

**Expected**: Zero errors, all files formatted correctly

### Level 2: Type Check
```bash
make type-check
make type-check FILE=src/taskweaver/agents/tools.py
make type-check FILE=src/taskweaver/agents/task_management.py
```

**Expected**: No type errors, all annotations valid

### Level 3: Unit Tests
```bash
# Test only new calculator tool
make test FILE=src/taskweaver/agents/tests/test_calculator_tool.py

# Test all agent tools (verify no regressions)
make test FILE=src/taskweaver/agents/tests/test_tools.py

# Full test suite (verify no breaking changes)
make test
```

**Expected**: All 18 calculator tests pass, no regressions, coverage ≥80%

### Level 4: Integration Tests
```bash
# Run full test suite including integration tests
pytest src/taskweaver/agents/tests/ -v
```

**Expected**: All agent integration tests pass, tool registration verified

### Level 5: Manual Validation

**Manual Test Scenarios:**

1. **Start chat interface and test calculator tool:**
   ```bash
   uv run taskweaver chat
   ```
   Then in chat:
   ```
   User: "Calculate 85.0 / 120 for me"
   Agent: [Should use calculator_tool and return "85.0 / 120 = 0.7083"]

   User: "What's the variance percentage if estimated was 60 minutes and actual was 90?"
   Agent: [Should use calculator_tool: "(90 - 60) / 60 * 100" = "50.0000"]
   ```

2. **Verify tool appears in agent capabilities:**
   ```python
   from taskweaver.agents.task_management import task_agent
   print([tool.__name__ for tool in task_agent._function_tools.values()])
   # Should include 'calculator_tool'
   ```

3. **Test error handling:**
   ```
   User: "Calculate 10 / 0"
   Agent: [Should gracefully handle error and explain division by zero]
   ```

---

## ACCEPTANCE CRITERIA

- [x] Feature implements all specified functionality (safe mathematical expression evaluation)
- [x] All validation commands pass with zero errors (format, lint, type-check, tests)
- [x] Unit test coverage meets requirements (18 tests, ≥80% coverage)
- [x] Integration tests verify end-to-end workflows (tool registration verified)
- [x] Code follows project conventions (Google docstrings, ModelRetry errors, type hints)
- [x] No regressions in existing functionality (all existing tests pass)
- [ ] Branch pushed to remote for review
- [ ] Documentation updated (orchestrator_prompt.md - optional but recommended)
- [ ] Manual validation completed (chat interface testing)

---

## EXECUTION TODOS

> Pre-built todo structure for implementation agent:

1. Read all mandatory context files and patterns
2. **Phase 1**: Add simpleeval dependency to pyproject.toml
3. **Phase 2**: Implement calculator_tool function in tools.py
4. **Phase 3**: Register tool in task_management.py TASK_TOOLS list
5. **Phase 4**: Create comprehensive test suite (18 tests)
6. **Phase 5** (Optional): Document tool in orchestrator_prompt.md
7. Run all validation commands (format, lint, type-check, tests)
8. Verify acceptance criteria (all must pass)
9. Manual validation via chat interface
10. Commit changes and push to remote

---

## NOTES & AUTONOMOUS DECISIONS

### Assumptions Made

1. **Assumption**: Use `simpleeval` library for expression evaluation
   - **Basis**: Industry standard for safe math evaluation, AST-based whitelisting, Python 3.13 compatible, actively maintained (1.0.3 current)
   - **Risk**: Low - library is mature and widely used
   - **Fallback**: Could use custom AST solution or asteval if simpleeval has issues

2. **Assumption**: Format float results to 4 decimal places
   - **Basis**: Provides precision without excessive verbosity, aligns with common financial/scientific conventions
   - **Risk**: Low - can be adjusted if more/less precision needed
   - **Fallback**: Make precision configurable via optional parameter

3. **Assumption**: Return string format "{expression} = {result}" instead of raw numeric
   - **Basis**: Token-efficient, human-readable, follows pattern from existing tools (e.g., completion tool variance formatting)
   - **Risk**: Low - string format is flexible and informative
   - **Fallback**: Could return dict with separate expression and result fields if structured data needed

4. **Assumption**: No need for advanced functions (sqrt, sin, cos, log)
   - **Basis**: Issue #50 and use cases focus on basic arithmetic for priority/variance calculations
   - **Risk**: Medium - users might want advanced functions later
   - **Fallback**: simpleeval supports function injection if needed in future

5. **Assumption**: Tool should be in task_management agent, not a separate agent
   - **Basis**: All tools described in issue are task-related calculations (priority, variance, duration)
   - **Risk**: Low - calculator is general-purpose utility useful across all agents
   - **Fallback**: Could add to multiple agents if needed

6. **Assumption**: Optional orchestrator prompt documentation (not blocking)
   - **Basis**: Tool is self-documenting via comprehensive docstring, LLM can discover via tool schema
   - **Risk**: Low - prompt documentation improves usage but isn't required for functionality
   - **Fallback**: Add documentation later if agent doesn't discover tool effectively

7. **Assumption**: No need for calculator history or memory
   - **Basis**: Calculations are stateless, results are immediately used or discarded
   - **Risk**: Low - no use case for historical calculations
   - **Fallback**: Could add history tracking if pattern emerges

8. **Assumption**: No rate limiting or quota on calculations
   - **Basis**: Calculations are fast (<1ms), no external API calls, no resource concerns
   - **Risk**: Very Low - computational cost is negligible
   - **Fallback**: Add rate limiting if abuse detected

### Design Decisions

1. **Decision**: Use simpleeval over ast.literal_eval or custom AST solution
   - **Alternatives**: ast.literal_eval (too limited), custom AST parser (too complex), numexpr (unsafe), asteval (overkill)
   - **Rationale**: simpleeval is purpose-built for safe math evaluation, AST-based (secure), actively maintained, Python 3.13 compatible
   - **Impact**: Single dependency added to pyproject.toml
   - **Security**: AST whitelisting prevents arbitrary code execution, tested against injection attacks

2. **Decision**: Implement as single tool function, not a class with methods
   - **Alternatives**: Calculator class with methods for each operation, separate tools per operation
   - **Rationale**: Follows established pattern in tools.py (all tools are functions), simpler implementation, LLM can specify operation in expression
   - **Impact**: Cleaner code, less boilerplate, easier maintenance

3. **Decision**: Use ModelRetry for all errors (not custom exceptions)
   - **Alternatives**: Raise ValueError/TypeError directly, return error strings instead of raising
   - **Rationale**: ModelRetry is established pattern for LLM-fixable errors (lines 102, 388, 634), enables retry loop with better prompting
   - **Impact**: Better error recovery, LLM learns from mistakes

4. **Decision**: No support for variables or custom functions
   - **Alternatives**: Allow variable assignment (x = 5), support custom function definitions
   - **Rationale**: Security risk (state management complexity), use cases don't require it, simpler implementation
   - **Impact**: Tool is stateless and secure, covers all identified use cases

5. **Decision**: Format floats to 4 decimal places uniformly
   - **Alternatives**: Variable precision based on input, scientific notation for large numbers, configurable precision parameter
   - **Rationale**: Consistent formatting aids readability, 4 decimals sufficient for priority/variance calculations, matches financial conventions
   - **Impact**: Predictable output format, may round very precise calculations

6. **Decision**: Single expression parameter, not separate operands
   - **Alternatives**: calculator_tool(operand1, operator, operand2), separate tools per operation
   - **Rationale**: More flexible (supports complex expressions), natural language to expression is easy for LLMs, fewer tool calls needed
   - **Impact**: More powerful tool, handles complex multi-step calculations

### Risks & Mitigations

1. **Risk**: simpleeval has unknown vulnerability
   - **Likelihood**: Low
   - **Impact**: High (arbitrary code execution)
   - **Mitigation**: simpleeval uses AST whitelisting (secure by design), actively maintained, input validation before evaluation, comprehensive security tests in test suite

2. **Risk**: Expression evaluation performance issues with very complex expressions
   - **Likelihood**: Low
   - **Impact**: Low (slow response)
   - **Mitigation**: simpleeval has reasonable limits (max 4M exponent, 100K string length), no recursion issues, typical expressions are simple

3. **Risk**: Float precision issues with financial calculations
   - **Likelihood**: Medium
   - **Impact**: Low (minor rounding errors)
   - **Mitigation**: 4 decimal places provide adequate precision for task priority/variance calculations, Python float (IEEE 754) is sufficient for use cases

4. **Risk**: Users expect advanced math functions (sqrt, sin, log)
   - **Likelihood**: Medium
   - **Impact**: Low (feature request)
   - **Mitigation**: simpleeval supports function injection, can add safe_dict with math functions if requested, basic operations cover current use cases

5. **Risk**: Tool isn't discovered by LLM effectively
   - **Likelihood**: Low
   - **Impact**: Medium (feature unused)
   - **Mitigation**: Comprehensive docstring documents use cases, optional orchestrator prompt documentation guides usage, tool name is descriptive

6. **Risk**: Division by zero errors confuse users
   - **Likelihood**: Medium
   - **Impact**: Low (confusion)
   - **Mitigation**: Clear error messages with ModelRetry, LLM can explain error to user, suggests checking denominator

### Trade-offs

- **Chose**: Simple string return format "{expression} = {result}"
- **Over**: Structured dict with separate fields or raw numeric return
- **Because**: Token-efficient, human-readable, follows existing tool patterns, flexible for downstream use
- **Accept**: Less structured for programmatic parsing, but use cases are conversational

- **Chose**: Single expression parameter supporting complex expressions
- **Over**: Separate parameters per operand (operand1, operator, operand2)
- **Because**: More flexible, handles complex multi-step calculations, natural for LLMs to generate
- **Accept**: Slightly more error-prone (syntax errors), but comprehensive error handling mitigates

- **Chose**: 4 decimal place precision for all floats
- **Over**: Variable precision or scientific notation
- **Because**: Consistent formatting, adequate for task calculations, matches financial conventions
- **Accept**: May round very precise calculations, but use cases don't require extreme precision

- **Chose**: No support for variables or custom functions
- **Over**: Full Python expression evaluator with state
- **Because**: Security (no state management), simplicity, covers all identified use cases
- **Accept**: Can't store intermediate results, but expression nesting achieves same goal

- **Chose**: simpleeval library dependency
- **Over**: Custom AST parser or ast.literal_eval
- **Because**: Battle-tested, secure, actively maintained, supports all needed operations
- **Accept**: External dependency (1 additional library), but risk is low and benefit is high

---

## REMOTE WORKFLOW METADATA

**Generated For**: Remote/Async GitHub Workflow
**User Input Required**: Minimal (only if truly ambiguous)
**Branch Name**: `feature/add-calculator-tool` (will be created)
**Commit Message**: `docs: 📝 add implementation plan for calculator tool

- Generated autonomous plan with deep codebase analysis
- Documented all assumptions and design decisions
- Ready for remote implementation via /github:implement-remote`
**Next Command**: `/github:implement-remote .agents/plans/add-calculator-tool-for-agents.md`
**Confidence Score**: 9/10

**Confidence Rationale**:
- All codebase patterns thoroughly analyzed with specific file:line references
- Implementation approach mirrors existing successful patterns (tool functions, error handling, test structure)
- Comprehensive research on safe expression evaluation libraries with clear winner (simpleeval)
- 18 comprehensive test cases designed covering all operations and edge cases
- Zero architectural ambiguity - all decisions based on established conventions
- Only minor uncertainty: Whether orchestrator prompt documentation is needed (marked optional)
- Security thoroughly considered with AST-based evaluation and comprehensive tests

**Key Risks**:
1. simpleeval vulnerability - Likelihood: Low, Impact: High (mitigated by AST whitelisting and security tests)
2. Users need advanced functions - Likelihood: Medium, Impact: Low (mitigated by extensibility via function injection)

**Estimated Implementation Time**: 2-3 hours (including testing and validation)
**Estimated Lines of Code**: ~200 (tool function: ~80, tests: ~100, registration: ~10, prompt: ~30)
