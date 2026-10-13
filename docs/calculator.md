# Calculator

The task-management agent uses `calculator_tool` for deterministic arithmetic. Its implementation is `src/taskweaver/agents/calculator.py`; the wrapper is in `src/taskweaver/agents/tools.py`. Stored priority and duration formulas remain in shared services.

## Interface and examples

```python
from taskweaver.agents.calculator import evaluate_expression

# evaluate_expression(expression: str) -> str
```

The result includes the original expression. Integers use integer formatting; floats use four decimal places.

| Expression | Returned string |
| --- | --- |
| `2 + 3 * 4` | `2 + 3 * 4 = 14` |
| `100 / 3` | `100 / 3 = 33.3333` |
| `(45 - 30) / 30 * 100` | `(45 - 30) / 30 * 100 = 50.0000` |

This is a Python interface and an agent tool, not a standalone CLI command.

## Allowed syntax

Use real numeric literals, parentheses, unary `+` and `-`, and binary `+`, `-`, `*`, `/`, `//`, `%`, and `**`. Normal arithmetic precedence applies.

Names, function calls (including `sqrt` and `abs`), attributes, indexing, containers, comparisons, strings, booleans, and complex numbers are rejected. The evaluator checks a Python AST allowlist, then uses `simpleeval` with no names or functions; it does not use Python `eval`.

## Limits

| Constant | Limit |
| --- | --- |
| `MAX_EXPRESSION_LENGTH` | 1,024 input characters, including surrounding whitespace |
| `MAX_AST_NODES` | 128 AST nodes, including expression and operator nodes |
| `MAX_INTEGER_BITS` | 4,096 bits per integer literal, intermediate value, or result |
| `MAX_EXPONENT` | Exponent magnitude at most 1,000 |

Integer powers with positive integer exponents also require `base.bit_length() * exponent <= 4096` before allocation. This conservative check can reject powers whose actual result would fit. All numeric values and results must be real and finite. Floats use ordinary floating-point arithmetic and rounding.

## Errors

- Empty, malformed, unsupported, nonfinite, or over-limit expressions raise `ValueError`. Numeric overflow and evaluation recursion errors are translated to `ValueError`.
- Division or modulo by zero, and zero raised to a negative power, raise `ZeroDivisionError`.
- `calculator_tool` translates these errors to PydanticAI `ModelRetry`, so the agent can correct its expression. It never substitutes a numeric result for an error.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the development checks.
