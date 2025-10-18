"""AI task master agent."""

__version__ = "0.1.0"


def example_function(value: str) -> str:
    """Return the input value unchanged.

    Args:
        value: The input string to return.

    Returns:
        The same string that was passed in.

    """
    return value


def main() -> None:
    """CLI entry point."""
    print("Hello from TaskWeaver!")
