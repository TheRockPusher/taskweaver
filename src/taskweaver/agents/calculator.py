"""Bounded, numeric-only arithmetic for agent calculations."""

import ast
import math
import operator

from simpleeval import SimpleEval

MAX_EXPRESSION_LENGTH = 1024
MAX_AST_NODES = 128
MAX_INTEGER_BITS = 4096
MAX_EXPONENT = 1000


def _check_number(value: object) -> int | float:
    """Reject nonnumeric, nonfinite, or oversized intermediate results."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        msg = "Only real numeric literals and arithmetic are allowed."
        raise ValueError(msg)
    if isinstance(value, int):
        if value.bit_length() > MAX_INTEGER_BITS:
            msg = f"Integer results must fit within {MAX_INTEGER_BITS} bits."
            raise ValueError(msg)
    elif not math.isfinite(value):
        msg = "Numeric values and results must be finite."
        raise ValueError(msg)
    return value


def _power(base: int | float, exponent: int | float) -> int | float:
    """Bound powers before allocating an integer result."""
    if abs(exponent) > MAX_EXPONENT:
        msg = f"Exponent magnitude cannot exceed {MAX_EXPONENT}."
        raise ValueError(msg)
    if (
        isinstance(base, int)
        and isinstance(exponent, int)
        and exponent > 0
        and base.bit_length() * exponent > MAX_INTEGER_BITS
    ):
        msg = f"Integer power exceeds the {MAX_INTEGER_BITS}-bit calculation limit."
        raise ValueError(msg)
    return _check_number(operator.pow(base, exponent))


class _NumericEvaluator(SimpleEval):
    """Validate every evaluated value, not only the final result."""

    def _eval(self, node: ast.AST) -> int | float:
        return _check_number(super()._eval(node))


def evaluate_expression(expression: str) -> str:
    """Evaluate bounded arithmetic without names, calls, or container access.

    Args:
        expression: Numeric arithmetic using +, -, *, /, //, **, %, and parentheses.

    Returns:
        The original expression and result, with floats formatted to four decimals.

    Raises:
        ValueError: For invalid syntax, unsupported operations, non-real or
            nonfinite numeric values or results, or resource limits.
        ZeroDivisionError: For division, modulo, or a negative power of zero.
    """
    if len(expression) > MAX_EXPRESSION_LENGTH:
        msg = f"Expression cannot exceed {MAX_EXPRESSION_LENGTH} characters."
        raise ValueError(msg)
    source = expression.strip()
    if not source:
        msg = "Expression cannot be empty."
        raise ValueError(msg)
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, RecursionError) as error:
        msg = "Invalid mathematical expression."
        raise ValueError(msg) from error

    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: _power,
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    allowed_nodes = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, *operators}
    for count, node in enumerate(ast.walk(tree), start=1):
        if count > MAX_AST_NODES:
            msg = f"Expression cannot exceed {MAX_AST_NODES} syntax nodes."
            raise ValueError(msg)
        if type(node) not in allowed_nodes:
            msg = "Only numbers and arithmetic operators (+, -, *, /, //, **, %) are allowed."
            raise ValueError(msg)
        if isinstance(node, ast.Constant):
            _check_number(node.value)

    evaluator = _NumericEvaluator(operators=operators, functions={}, names={})
    try:
        result = evaluator.eval(source, previously_parsed=tree.body)
    except (OverflowError, RecursionError) as error:
        msg = "Expression exceeds numeric calculation limits."
        raise ValueError(msg) from error
    formatted = f"{result:.4f}" if isinstance(result, float) else str(result)
    return f"{expression} = {formatted}"
