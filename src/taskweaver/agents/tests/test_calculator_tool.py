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
