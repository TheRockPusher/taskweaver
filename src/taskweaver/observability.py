"""Optional, explicit Langfuse instrumentation for local or remote hosts."""

import os

from pydantic_ai.agent import Agent


def start_langfuse() -> None:
    """Authenticate explicitly configured tracing before enabling instrumentation."""
    missing = [name for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY") if not os.getenv(name)]
    if missing:
        msg = f"Langfuse tracing requires {', '.join(missing)}."
        raise RuntimeError(msg)
    try:
        from langfuse import get_client  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        msg = "Install taskweaver[observability] to enable Langfuse tracing."
        raise RuntimeError(msg) from exc

    if not get_client().auth_check():
        msg = "Langfuse authentication did not succeed. Check LANGFUSE_HOST, connectivity, and credentials."
        raise RuntimeError(msg)
    Agent.instrument_all()
