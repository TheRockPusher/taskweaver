# Feature: Calculator Tool for Mathematical Operations

> **IMPORTANT**: Validate documentation and codebase patterns before implementing.
> Pay attention to naming of existing utils, types, and models.
> Import from correct files.

## Overview

**Description**: Add a safe mathematical expression evaluator tool that enables the orchestrator agent to perform calculations for task estimation, priority scoring, time conversions, and value calculations.

**Problem**: The orchestrator agent currently lacks the ability to perform mathematical calculations when helping users estimate task durations, compute priority scores from multi-dimensional values, convert time units, or calculate budget/financial impact for value scoring. Users must perform these calculations externally, breaking the conversational flow.

**Solution**: Implement a `calculator_tool` using the `simpleeval` library (safe ast-based expression evaluator) that accepts mathematical expressions as strings and returns numeric results. The tool will integrate with the task management agent's existing tool suite and follow established error handling patterns using `ModelRetry` for invalid input.

## Metadata

| Field | Value |
|-------|-------|
| Type | New Capability |
| Complexity | Low |
| Systems Affected | Task management agent, agent tools |
| Dependencies | simpleeval (new external library) |

---

## CONTEXT REFERENCES

### Mandatory Reading (READ BEFORE IMPLEMENTING)

- `src/taskweaver/agents/tools.py:1-709` - Why: Complete tool implementation patterns, error handling with ModelRetry, docstring style
- `src/taskweaver/agents/tools.py:60-103` - Why: Example tool structure (create_task_tool) - signature, validation, error handling
- `src/taskweaver/agents/tests/test_tools.py:1-344` - Why: Test patterns, fixtures (deps, ctx), test class organization, pytest patterns
- `src/taskweaver/agents/tests/test_tools.py:25-46` - Why: Fixture definitions for deps and ctx (must mirror this pattern)
- `src/taskweaver/agents/task_management.py:1-50` - Why: Tool registration pattern in TASK_TOOLS list
- `src/taskweaver/agents/prompts/task.md:1-473` - Why: Agent prompt structure for documenting new tools
- `pyproject.toml:31-43` - Why: Dependency specification format

### New Files to Create

- None (all modifications to existing files)

### Files to Modify

1. `pyproject.toml` - Add simpleeval dependency
2. `src/taskweaver/agents/tools.py` - Add calculator_tool implementation
3. `src/taskweaver/agents/task_management.py` - Register calculator_tool in TASK_TOOLS
4. `src/taskweaver/agents/prompts/task.md` - Document calculator_tool usage
5. `src/taskweaver/agents/tests/test_tools.py` - Add TestCalculatorTool test class

### Documentation References

- [simpleeval PyPI](https://pypi.org/project/simpleeval/) - Why: Library API and usage examples
- [simpleeval GitHub](https://github.com/danthedeckie/simpleeval) - Why: Security features and limitations
- [Python AST Module](https://docs.python.org/3/library/ast.html) - Why: Understanding ast-based evaluation approach
- [Stack Overflow: Safely evaluate expressions](https://stackoverflow.com/questions/43836866/safely-evaluate-simple-string-equation) - Why: Common patterns and gotchas

### Patterns to Follow

**Tool Signature Pattern** (from tools.py:60-103):
```python
def calculator_tool(
    ctx: RunContext[TaskDependencies],
    expression: str,
) -> str:
    """Tool docstring with Google-style format.

    Args:
        ctx: Runtime context containing TaskDependencies.
        expression: Mathematical expression to evaluate.

    Returns:
        Result as string with formatted output.

    Raises:
        ModelRetry: If expression is invalid. LLM receives error and can retry.
    """
```

**Error Handling Pattern** (from tools.py:101-102):
```python
try:
    # Tool logic
except (ValidationError, ValueError) as e:
    raise ModelRetry(str(e)) from e
```

**Test Pattern** (from test_tools.py:62-88):
```python
class TestCalculatorTool:
    """Tests for calculator_tool."""

    def test_calculator_basic_arithmetic(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test basic arithmetic operations."""
        result = calculator_tool(ctx, "2 + 2")
        assert "4" in result

    def test_calculator_invalid_expression_raises(self, ctx: RunContext[TaskDependencies]) -> None:
        """Test invalid expression raises ModelRetry."""
        with pytest.raises(ModelRetry):
            calculator_tool(ctx, "invalid syntax")
```

### Boundaries

**ALWAYS:**
- Use `ModelRetry` for all invalid input (never return error strings that halt agent)
- Include comprehensive Google-style docstrings with Args/Returns/Raises/Example
- Add type hints to all parameters and return values
- Write tests for success cases, edge cases, and error conditions
- Maintain ≥80% test coverage (project requirement)
- Follow existing tool patterns exactly (signature, error handling, documentation)
- Run all validation commands before committing

**ASK FIRST:**
- None (feature is well-defined and low-complexity)

**NEVER:**
- Use `eval()` or `exec()` for expression evaluation (security risk)
- Return error messages as strings (breaks agent retry mechanism)
- Skip tests or reduce coverage below 80%
- Modify tool signatures in ways that break existing patterns
- Add dependencies without updating pyproject.toml

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation
Add external dependency and understand security model.

**Tasks:**
- Add `simpleeval` to pyproject.toml dependencies
- Validate dependency installation with `uv sync`
- Review simpleeval API and security features

### Phase 2: Core Implementation
Implement calculator_tool following existing patterns.

**Tasks:**
- Add calculator_tool to tools.py
- Follow tool signature pattern exactly
- Implement safe evaluation with simpleeval.simple_eval
- Add comprehensive error handling with ModelRetry
- Format output for readability

### Phase 3: Integration
Register tool and update documentation.

**Tasks:**
- Add calculator_tool to TASK_TOOLS list in task_management.py
- Update task.md agent prompt with tool documentation
- Follow existing tool documentation format

### Phase 4: Testing & Validation
Comprehensive test coverage and validation.

**Tasks:**
- Add TestCalculatorTool class to test_tools.py
- Test basic arithmetic (addition, subtraction, multiplication, division)
- Test complex expressions (order of operations, parentheses)
- Test edge cases (division by zero, empty string, malformed syntax)
- Test floating point results
- Verify ModelRetry is raised for invalid input
- Run all validation commands

---

## STEP-BY-STEP TASKS

> Execute every task in order, top to bottom. Each task is atomic and testable.

### UPDATE pyproject.toml

- **IMPLEMENT**: Add `simpleeval>=1.0.0` to dependencies list after line 42
- **PATTERN**: `src/taskweaver/pyproject.toml:31-43` (dependency format)
- **LOCATION**: Insert alphabetically between existing dependencies
- **GOTCHA**: Use `>=` version constraint, not exact version pinning
- **VALIDATE**: `uv sync` (verify dependency resolves and installs)

---

### UPDATE src/taskweaver/agents/tools.py

**Location**: After `get_blocked_tool` (around line 680), before end of file

- **IMPLEMENT**: Add calculator_tool function with complete implementation
- **PATTERN**: Mirror `create_task_tool` structure (lines 60-103) for signature and error handling
- **IMPORTS**: Add at top of file:
  ```python
  from simpleeval import simple_eval
  ```
- **SIGNATURE**:
  ```python
  def calculator_tool(
      ctx: RunContext[TaskDependencies],
      expression: str,
  ) -> str:
  ```
- **DOCSTRING**: Google-style with Args/Returns/Raises/Example sections
- **LOGIC**:
  1. Validate expression is not empty/whitespace (raise ModelRetry if invalid)
  2. Call `simple_eval(expression)` to evaluate
  3. Catch exceptions (ZeroDivisionError, SyntaxError, etc.) and raise ModelRetry
  4. Format result with 4 decimal places for floats
  5. Return formatted string: `"{expression} = {result}"`
- **ERROR HANDLING**: Wrap in try/except, raise ModelRetry with descriptive message
- **GOTCHA**: simpleeval already handles division by zero, malformed syntax, etc.
- **EXAMPLE IMPLEMENTATION**:
  ```python
  def calculator_tool(
      ctx: RunContext[TaskDependencies],
      expression: str,
  ) -> str:
      """Evaluate mathematical expressions safely for task calculations.

      Enables the agent to perform calculations for:
      - Time unit conversions (e.g., "2.5 * 60" for hours to minutes)
      - Priority score computations (e.g., "85.0 / 120")
      - Multi-dimensional value scoring (e.g., "(85 * 0.35) + (65 * 0.30) + (95 * 0.35)")
      - Budget and financial impact calculations

      Uses ast-based safe evaluation (no code execution). Supports:
      - Arithmetic: +, -, *, /, **, %
      - Parentheses for order of operations
      - Integers and floating-point numbers

      Args:
          ctx: Runtime context containing TaskDependencies.
          expression: Mathematical expression to evaluate (e.g., "(92 * 0.35) + (78 * 0.30)").

      Returns:
          Formatted calculation result as string: "{expression} = {result}".

      Raises:
          ModelRetry: If expression is invalid, empty, or causes evaluation error.
              LLM receives error message and can retry with corrected expression.

      Example:
          >>> calculator_tool(ctx, expression="(92 * 0.35) + (78 * 0.30) + (88 * 0.35)")
          "(92 * 0.35) + (78 * 0.30) + (88 * 0.35) = 86.4000"

          >>> calculator_tool(ctx, expression="85.0 / 120")
          "85.0 / 120 = 0.7083"

          >>> calculator_tool(ctx, expression="2.5 * 60")
          "2.5 * 60 = 150.0000"
      """
      # Validate input
      if not expression or not expression.strip():
          raise ModelRetry("Expression cannot be empty") from None

      try:
          # Safe evaluation using ast-based simpleeval
          result = simple_eval(expression.strip())

          # Format result
          if isinstance(result, (int, float)):
              # Format floats with 4 decimal places, integers as-is
              formatted_result = f"{result:.4f}" if isinstance(result, float) else str(result)
              return f"{expression} = {formatted_result}"

          # Non-numeric result (shouldn't happen with math expressions)
          return f"{expression} = {result}"

      except ZeroDivisionError as e:
          raise ModelRetry(f"Division by zero in expression: {expression}") from e
      except (SyntaxError, TypeError, ValueError, NameError) as e:
          raise ModelRetry(f"Invalid mathematical expression: {expression}. Error: {e}") from e
  ```
- **VALIDATE**: `make format` (ensure code formatting)

---

### UPDATE src/taskweaver/agents/task_management.py

- **IMPLEMENT**: Add `calculator_tool` to imports (line 6-22)
- **PATTERN**: Alphabetical import order within tool imports
- **LOCATION**: Add after `add_dependency_tool,` in import list
- **IMPORT LINE**: `calculator_tool,`
- **IMPLEMENT**: Add `calculator_tool` to TASK_TOOLS list (line 24-42)
- **PATTERN**: Insert alphabetically in CRUD section (after `create_task_tool`)
- **LOCATION**: Line ~29, after `create_task_tool,`
- **LIST ENTRY**: `calculator_tool,`
- **GOTCHA**: Maintain trailing comma on all list entries
- **VALIDATE**: `make lint-check` (verify import order and syntax)

---

### UPDATE src/taskweaver/agents/prompts/task.md

**Location**: After tool #13 (get_blocked_tool), around line 205

- **IMPLEMENT**: Add tool documentation section for calculator_tool
- **PATTERN**: Mirror format of other tool docs (lines 19-204) - numbered heading, purpose, parameters, when to use, examples
- **STRUCTURE**:
  ```markdown
  ### 14. calculator_tool(expression: str)

  **Purpose**: Evaluate mathematical expressions for task calculations.

  **Parameters**:
  - `expression`: Mathematical expression to evaluate (e.g., "(92 * 0.35) + (78 * 0.30)")

  **Supported operations**:
  - Arithmetic: `+`, `-`, `*`, `/`, `**` (power), `%` (modulo)
  - Parentheses for order of operations
  - Integers and floating-point numbers

  **When to use**:
  - Converting time units (hours to minutes: "2.5 * 60")
  - Computing weighted value scores: "(financial * 0.35) + (knowledge * 0.30) + (strategic * 0.35)"
  - Calculating priority ratios: "85.0 / 120"
  - Financial calculations: "(revenue - cost) / time_investment"
  - Any arithmetic needed for task estimation or prioritization

  **Safety**: Uses ast-based evaluation. No code execution. Division by zero handled gracefully.

  **Examples**:
  ```
  calculator_tool(expression="(92 * 0.35) + (78 * 0.30) + (88 * 0.35)")
  → "(92 * 0.35) + (78 * 0.30) + (88 * 0.35) = 86.4000"

  calculator_tool(expression="85.0 / 120")
  → "85.0 / 120 = 0.7083"

  calculator_tool(expression="2.5 * 60")
  → "2.5 * 60 = 150.0000"
  ```
  ```
- **GOTCHA**: Maintain consistent heading numbering (this is tool #14)
- **VALIDATE**: Visual inspection of markdown formatting

---

### CREATE tests in src/taskweaver/agents/tests/test_tools.py

**Location**: End of file, after TestUpdateTaskStatusTool class (after line 344)

- **IMPLEMENT**: Add comprehensive test class TestCalculatorTool
- **PATTERN**: Mirror TestUpdateTaskTool structure (lines 62-88) - test class with multiple test methods
- **IMPORTS**: None needed (simpleeval imported via tools module)
- **FIXTURES**: Use existing `ctx` fixture (lines 39-46) - do not create new fixtures
- **TEST CLASS**:
  ```python
  class TestCalculatorTool:
      """Tests for calculator_tool."""

      def test_calculator_basic_addition(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test basic addition."""
          result = calculator_tool(ctx, "2 + 2")
          assert "2 + 2 = 4" in result

      def test_calculator_basic_subtraction(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test basic subtraction."""
          result = calculator_tool(ctx, "10 - 3")
          assert "10 - 3 = 7" in result

      def test_calculator_basic_multiplication(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test basic multiplication."""
          result = calculator_tool(ctx, "5 * 6")
          assert "5 * 6 = 30" in result

      def test_calculator_basic_division(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test basic division with float result."""
          result = calculator_tool(ctx, "85.0 / 120")
          assert "85.0 / 120" in result
          assert "0.7083" in result

      def test_calculator_complex_expression(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test complex weighted calculation."""
          result = calculator_tool(ctx, "(92 * 0.35) + (78 * 0.30) + (88 * 0.35)")
          assert "86.4" in result

      def test_calculator_order_of_operations(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test order of operations with parentheses."""
          result = calculator_tool(ctx, "2 + 3 * 4")
          assert "2 + 3 * 4 = 14" in result

          result_parens = calculator_tool(ctx, "(2 + 3) * 4")
          assert "(2 + 3) * 4 = 20" in result_parens

      def test_calculator_power_operation(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test exponentiation."""
          result = calculator_tool(ctx, "2 ** 8")
          assert "2 ** 8 = 256" in result

      def test_calculator_modulo_operation(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test modulo operation."""
          result = calculator_tool(ctx, "17 % 5")
          assert "17 % 5 = 2" in result

      def test_calculator_time_conversion(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test time conversion (hours to minutes)."""
          result = calculator_tool(ctx, "2.5 * 60")
          assert "2.5 * 60" in result
          assert "150" in result

      def test_calculator_division_by_zero_raises(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test division by zero raises ModelRetry."""
          with pytest.raises(ModelRetry, match="Division by zero"):
              calculator_tool(ctx, "10 / 0")

      def test_calculator_empty_expression_raises(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test empty expression raises ModelRetry."""
          with pytest.raises(ModelRetry, match="cannot be empty"):
              calculator_tool(ctx, "")

      def test_calculator_whitespace_only_raises(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test whitespace-only expression raises ModelRetry."""
          with pytest.raises(ModelRetry, match="cannot be empty"):
              calculator_tool(ctx, "   ")

      def test_calculator_invalid_syntax_raises(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test malformed expression raises ModelRetry."""
          with pytest.raises(ModelRetry, match="Invalid mathematical expression"):
              calculator_tool(ctx, "2 + + 3")

      def test_calculator_undefined_variable_raises(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test undefined variable raises ModelRetry."""
          with pytest.raises(ModelRetry, match="Invalid mathematical expression"):
              calculator_tool(ctx, "x + 5")

      def test_calculator_float_precision(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test float results formatted to 4 decimal places."""
          result = calculator_tool(ctx, "1 / 3")
          assert "1 / 3" in result
          assert "0.3333" in result

      def test_calculator_negative_numbers(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test negative number handling."""
          result = calculator_tool(ctx, "-5 + 3")
          assert "-5 + 3 = -2" in result

      def test_calculator_large_expression(self, ctx: RunContext[TaskDependencies]) -> None:
          """Test complex multi-operation expression."""
          result = calculator_tool(ctx, "((100 - 20) * 0.5) + (30 / 2) - 10")
          assert "45" in result
  ```
- **IMPORTS NEEDED**: Add to top of file if missing:
  ```python
  from taskweaver.agents.tools import calculator_tool
  ```
- **COVERAGE**: 18 test cases covering success, edge cases, errors
- **GOTCHA**: Tests must use existing `ctx` fixture, not create custom mocks
- **VALIDATE**: `make test FILE=src/taskweaver/agents/tests/test_tools.py` (run tests)

---

## TESTING STRATEGY

### Unit Tests
**Scope**: Comprehensive coverage of calculator_tool in isolation

**Test Categories**:
1. **Basic Operations** (5 tests): Addition, subtraction, multiplication, division, modulo
2. **Complex Expressions** (4 tests): Parentheses, order of operations, nested operations, weighted calculations
3. **Edge Cases** (6 tests): Division by zero, empty input, whitespace, invalid syntax, undefined variables, negative numbers
4. **Formatting** (2 tests): Float precision (4 decimals), integer formatting
5. **Real-world Use Cases** (1 test): Time conversion example from issue

**Expected Coverage**: 100% of calculator_tool (all branches covered)

### Integration Tests
**Scope**: Not required (tool has no external dependencies beyond simpleeval)

**Rationale**: calculator_tool is stateless and has no database/file interactions. Unit tests provide complete validation.

### Edge Cases
- **Division by zero**: `"10 / 0"` → ModelRetry
- **Empty expression**: `""` → ModelRetry
- **Whitespace only**: `"   "` → ModelRetry
- **Malformed syntax**: `"2 + + 3"` → ModelRetry
- **Undefined variables**: `"x + 5"` → ModelRetry (simpleeval blocks by default)
- **Invalid characters**: `"import os"` → ModelRetry (simpleeval blocks statements)
- **Very long expressions**: Handled by simpleeval's built-in length limits (100k chars)
- **Extremely large results**: Python handles arbitrary precision integers
- **Negative numbers**: `"-5 + 3"` → `-2`
- **Floating point precision**: Results formatted to 4 decimal places

---

## VALIDATION COMMANDS

> Execute every command to ensure zero regressions.

### Level 1: Syntax & Style
```bash
# Format code with Ruff
make format

# Check formatting
make format-check

# Lint with Ruff (comprehensive ruleset)
make lint-check
```

### Level 2: Type Check
```bash
# Static type analysis with Ty
make type-check
```

### Level 3: Unit Tests
```bash
# Run all tests with coverage (must maintain ≥80%)
make test

# Run only calculator tool tests
make test FILE=src/taskweaver/agents/tests/test_tools.py::TestCalculatorTool

# Verify coverage report shows 100% coverage for calculator_tool
uv run pytest --cov=taskweaver.agents.tools --cov-report=term-missing -k calculator_tool
```

### Level 4: Integration Tests
```bash
# Not applicable (tool has no integration points beyond library)
```

### Level 5: Manual Validation
1. **Start interactive chat**: `uv run taskweaver chat --db /tmp/test.db`
2. **Test calculator invocation**:
   - Input: "Calculate (85 * 0.35) + (65 * 0.30) + (95 * 0.35)"
   - Expected: Agent uses calculator_tool and returns result ~85.75
3. **Test time conversion**:
   - Input: "Convert 2.5 hours to minutes"
   - Expected: Agent uses calculator_tool with "2.5 * 60" → 150 minutes
4. **Test error handling**:
   - Input: "Calculate 10 divided by 0"
   - Expected: Agent receives ModelRetry, explains division by zero
5. **Test priority calculation**:
   - Input: "What's the priority for a task with value 85 and duration 120 minutes?"
   - Expected: Agent uses calculator_tool with "85 / 120" → ~0.708

---

## ACCEPTANCE CRITERIA

- [ ] `simpleeval` dependency added to pyproject.toml and installs successfully
- [ ] `calculator_tool` function implemented in tools.py with complete Google-style docstring
- [ ] Tool follows exact signature pattern: `(ctx: RunContext[TaskDependencies], expression: str) -> str`
- [ ] All invalid input raises `ModelRetry` (never returns error strings)
- [ ] Float results formatted to 4 decimal places
- [ ] `calculator_tool` registered in TASK_TOOLS list in task_management.py
- [ ] Tool documented in task.md agent prompt with examples
- [ ] TestCalculatorTool class added with 18 comprehensive test cases
- [ ] All validation commands pass with zero errors:
  - `make format-check` ✓
  - `make lint-check` ✓
  - `make type-check` ✓
  - `make test` ✓ (coverage ≥80% maintained)
- [ ] Manual testing confirms agent can invoke calculator_tool successfully
- [ ] No regressions in existing functionality (all existing tests still pass)
- [ ] Code follows project conventions (Google docstrings, type hints, error patterns)

---

## EXECUTION TODOS

> Pre-built todo structure for implementation agent:

1. Read all mandatory context files (tools.py, test_tools.py, task_management.py)
2. Phase 1: Add simpleeval dependency to pyproject.toml
3. Phase 1: Run `uv sync` to verify dependency installation
4. Phase 2: Implement calculator_tool in tools.py
5. Phase 2: Add import for simpleeval at top of tools.py
6. Phase 3: Add calculator_tool to imports in task_management.py
7. Phase 3: Register calculator_tool in TASK_TOOLS list
8. Phase 3: Document calculator_tool in task.md prompt
9. Phase 4: Add TestCalculatorTool class with 18 test cases
10. Phase 4: Add calculator_tool import to test_tools.py
11. Run Level 1 validation: `make format && make lint-check`
12. Run Level 2 validation: `make type-check`
13. Run Level 3 validation: `make test`
14. Run Level 5 manual validation (interactive chat testing)
15. Verify all acceptance criteria checked

---

## NOTES

### Design Decisions

**Library Choice: simpleeval vs alternatives**
- **Chosen**: `simpleeval`
- **Rationale**:
  - Actively maintained (security updates in 2024-2025)
  - Built on Python's ast module (safe by design)
  - Simple API that fits use case perfectly
  - Handles all edge cases (division by zero, malformed syntax, security)
  - Well-documented with clear security features
- **Rejected alternatives**:
  - `ast.literal_eval`: Cannot evaluate expressions with operators
  - `sympy`: Overkill for basic arithmetic, heavy dependency
  - `asteval`: More complex API than needed
  - Custom ast parser: Would require extensive security testing

**Return Type: str vs float**
- **Chosen**: `str` with formatted output `"{expression} = {result}"`
- **Rationale**:
  - Provides context (user sees what was calculated)
  - Consistent with other tools that return human-readable strings
  - Agent can parse numeric value if needed for further calculations
  - Better for conversational UX

**Error Handling: ModelRetry vs error strings**
- **Chosen**: Always raise `ModelRetry` for invalid input
- **Rationale**:
  - Enables agent retry mechanism (LLM can fix and retry)
  - Consistent with all other tools in tools.py
  - Prevents agent getting stuck on bad input
  - Pattern established by project conventions

### Security Considerations

**Expression Evaluation Safety**:
- simpleeval uses ast-based whitelisting (not blacklisting)
- No code execution possible (statements, imports blocked)
- Built-in protection against:
  - Infinite loops (max power limit: 4,000,000)
  - Memory exhaustion (string length limit: 100k chars)
  - Attribute access to dangerous objects (`_` prefix blocked)
  - Code injection (only literal expressions allowed)

**Known Limitations**:
- simpleeval does not support user-defined functions (by design)
- No access to Python built-ins beyond basic math operations
- No variable assignment or complex data structures
- These limitations are features (reduce attack surface)

### Trade-offs

**Precision**: 4 decimal places chosen as balance between readability and accuracy. Can be adjusted if needed for financial calculations requiring more precision.

**Performance**: simpleeval adds negligible overhead (~microseconds per evaluation). Not a bottleneck for task management use case.

**Dependency Weight**: simpleeval is lightweight (~50KB), zero transitive dependencies. Acceptable trade-off for safety.

### Future Enhancements (Out of Scope)

- Support for named variables (e.g., `calculator_tool(expression="value / duration", variables={"value": 85, "duration": 120})`)
- Support for custom functions (e.g., min, max, abs)
- Multi-line calculations with intermediate results
- Statistical functions (mean, median, std dev)

These can be added incrementally without breaking changes to current API.

### References

- [ASTEVAL: Minimal Python AST Evaluator](https://lmfit.github.io/asteval/)
- [asteval · PyPI](https://pypi.org/project/asteval/)
- [GitHub - newville/asteval](https://github.com/newville/asteval)
- [Python ast — Abstract syntax trees](https://docs.python.org/3/library/ast.html)
- [simpleeval · PyPI](https://pypi.org/project/simpleeval/)
- [Stack Overflow: Evaluating mathematical expressions](https://stackoverflow.com/questions/2371436/evaluating-a-mathematical-expression-in-a-string)
- [Stack Overflow: Safely evaluate simple equation](https://stackoverflow.com/questions/43836866/safely-evaluate-simple-string-equation)
- [Real Python: Python eval()](https://realpython.com/python-eval-function/)
