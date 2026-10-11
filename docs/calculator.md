# Calculator: completed design reference

The calculator is implemented in `src/taskweaver/agents/calculator.py`, wrapped by `calculator_tool` in `agents/tools.py`, and registered with the task-management agent. It supplies deterministic arithmetic for conversational calculations; persisted MCDA/CD3 and duration-learning formulas remain service-owned, not delegated to model arithmetic.

## Interface and usage

`evaluate_expression(expression: str) -> str` returns the original expression followed by ` = RESULT`. Integers retain integer formatting; floats use four decimal places. Examples by interface definition:

- `2 + 3 * 4` → `2 + 3 * 4 = 14`
- `100 / 3` → `100 / 3 = 33.3333`
- `(45 - 30) / 30 * 100` → `(45 - 30) / 30 * 100 = 50.0000`

Allowed operations: numeric real literals, parentheses, unary `+`/`-`, binary `+`, `-`, `*`, `/`, `//`, `%`, `**`. No names, functions (including `sqrt`/`abs`), attributes, indexing, containers, comparisons, strings, booleans, or complex numbers are supported. This is an agent tool/Python interface, not a standalone CLI command.

## Security/resource boundaries

The implementation parses an expression AST, checks an exact node/operator allowlist, and uses `simpleeval` with empty names/functions and explicit operators. It does not use Python `eval` or execute arbitrary source.

- Maximum input length: 1,024 characters.
- Maximum AST size: 128 nodes.
- Integer literals/intermediates/results: at most 4,096 bits.
- Exponent magnitude: at most 1,000, with an integer power-size precheck before allocation.
- Every evaluated numeric value must be real, finite, and within the limits.

Malformed/unsupported/resource-exceeding expressions raise `ValueError`; zero division/modulo/negative powers of zero raise `ZeroDivisionError`. The tool wrapper translates fixable errors to PydanticAI `ModelRetry`, rather than fabricating a numeric result. These bounds reduce resource risk; this is not a general-purpose sandbox or arbitrary-code execution service. Floats retain ordinary floating-point rounding limitations.

## Acceptance reference

Regression coverage should retain operator precedence, unary operations, parentheses, integer/float formatting, zero division, syntax failures, rejection of executable/non-numeric constructs, finite-number checking, and each input/AST/integer/exponent bound. Agent registration and error translation must remain covered independently of provider behavior.

Core verification recorded calculator coverage at 100%; that historical observation is not a claim that new combined gates or a native/provider run were executed for this documentation change. See [CONTRIBUTING.md](../../CONTRIBUTING.md) for the overall check workflow. This reference replaces the obsolete implementation plan, not a pending feature proposal.
