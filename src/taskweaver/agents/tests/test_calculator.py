"""Regression coverage for numeric arithmetic and bounded evaluation."""

import pytest

from taskweaver.agents.calculator import evaluate_expression


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 3 * 4", "14"),
        ("(2 + 3) * 4", "20"),
        ("((10 - 5) * 2) + 3", "13"),
        ("-2 ** 2", "-4"),
        ("(-2) ** 2", "4"),
        ("2 ** 3 ** 2", "512"),
        ("2 + + 2", "4"),
        ("5 - 10", "-5"),
        ("17 // 5", "3"),
        ("-17 // 5", "-4"),
        ("-17 % 5", "3"),
        ("17 % 5", "2"),
        ("2 ** -3", "0.1250"),
        ("9 ** 0.5", "3.0000"),
        ("3.5 * 2.5", "8.7500"),
        ("(90 - 60) / 60 * 100", "50.0000"),
        ("85.0 / 120", "0.7083"),
        ("1e2 + 0x10", "116.0000"),
        ("9007199254740993 + 1", "9007199254740994"),
        ("  2 + 2  ", "4"),
        ("(92*0.35) + (78*0.30) + (88*0.35)", "86.4000"),
        ("-5 + 3", "-2"),
        ("10 / 3", "3.3333"),
        ("1000000 * 1000", "1000000000"),
    ],
)
def test_arithmetic_results(expression: str, expected: str) -> None:
    assert evaluate_expression(expression) == f"{expression} = {expected}"


@pytest.mark.parametrize("expression", ["10 / 0", "10 // 0", "10 % 0", "0 ** -1"])
def test_zero_denominators(expression: str) -> None:
    with pytest.raises(ZeroDivisionError):
        evaluate_expression(expression)


@pytest.mark.parametrize("expression", ["", "   ", "\n\t"])
def test_empty_expression(expression: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        evaluate_expression(expression)


@pytest.mark.parametrize("expression", ["2 + * 2", "(2 + 3", "1; 2", "value = 2", "1\n2"])
def test_invalid_syntax(expression: str) -> None:
    with pytest.raises(ValueError, match="Invalid mathematical expression"):
        evaluate_expression(expression)


@pytest.mark.parametrize(
    "expression",
    [
        "'abc'",
        "'abc' * 1000000000",
        "b'abc'",
        "True",
        "False",
        "None",
        "1j",
        "1 + 2j",
        "x + 1",
        "nan",
        "inf",
        "rand()",
        "int('3')",
        "abs(-1)",
        "__import__('os').system('echo unsafe')",
        "(1).__class__",
        "(1).real",
        "[1, 2][0]",
        "[x for x in [1]]",
        "(x for x in [1])",
        "{1: 2}",
        "{1, 2}",
        "(1, 2)",
        "lambda: 1",
        "f'{1}'",
        "1 if 1 else 2",
        "1 < 2",
        "1 and 2",
        "not 1",
        "1 << 1000000000",
        "1 | 2",
        "~1",
        "(x := 1)",
    ],
)
def test_rejects_non_arithmetic(expression: str) -> None:
    with pytest.raises(ValueError, match="Only"):
        evaluate_expression(expression)


@pytest.mark.parametrize(
    ("expression", "error_category"),
    [
        ("1e309", "finite"),
        ("1e308 * 1e308", "finite"),
        ("(1e308 * 1e308) / 1e308", "finite"),
        ("1e308 ** 2", "numeric calculation limits"),
        ("(-1) ** 0.5", "real numeric"),
    ],
)
def test_rejects_nonfinite_or_complex_results(expression: str, error_category: str) -> None:
    with pytest.raises(ValueError, match=error_category):
        evaluate_expression(expression)


@pytest.mark.parametrize("expression", ["2 ** 1001", "2 ** -1001", "2 ** (2 ** 10)", "10 ** 1000000000"])
def test_exponent_limits(expression: str) -> None:
    with pytest.raises(ValueError, match="Exponent magnitude"):
        evaluate_expression(expression)


def test_integer_power_limit() -> None:
    with pytest.raises(ValueError, match="Integer power exceeds"):
        evaluate_expression("(2 ** 1000) ** 5")


def test_integer_intermediate_limit() -> None:
    product = " * ".join(["(2 ** 1000)"] * 5)
    with pytest.raises(ValueError, match="Integer results must fit"):
        evaluate_expression(f"({product}) % 2")


def test_expression_length_limit() -> None:
    with pytest.raises(ValueError, match="characters"):
        evaluate_expression("1" + " " * 1024)


def test_syntax_node_limit() -> None:
    with pytest.raises(ValueError, match="syntax nodes"):
        evaluate_expression(" + ".join(["1"] * 44))


def test_parser_nesting_limit() -> None:
    with pytest.raises(ValueError, match="Invalid mathematical expression"):
        evaluate_expression("(" * 250 + "1" + ")" * 250)


def test_valid_resource_boundaries() -> None:
    exponent = "2 ** 1000"
    assert evaluate_expression(exponent) == f"{exponent} = {2**1000}"
    nodes = " + ".join(["1"] * 43)
    assert evaluate_expression(nodes) == f"{nodes} = 43"
    length = "1" + " " * 1023
    assert evaluate_expression(length) == f"{length} = 1"
