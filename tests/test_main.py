"""Tests for TaskWeaver."""

import pytest

from taskweaver import example_function, main


def test_example_function() -> None:
    """Test example_function."""
    assert example_function("test") == "test"


def test_main(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entry point."""
    main()
    captured = capsys.readouterr()
    assert "Hello from TaskWeaver!" in captured.out
