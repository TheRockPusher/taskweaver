"""TaskWeaver - AI-powered task organizer with intelligent decomposition.

This package provides tools for task management, decomposition, and skill-based learning.
"""

from importlib.metadata import version

from taskweaver.cli import main

__version__ = version("taskweaver")

__all__ = [
    "__version__",
    "main"
]
