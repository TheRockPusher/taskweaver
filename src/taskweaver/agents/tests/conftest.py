"""Shared fixtures for agents tests."""

from pathlib import Path

import pytest


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide temporary database path."""
    return tmp_path / "test.db"
