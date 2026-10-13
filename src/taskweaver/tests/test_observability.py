"""Consumer-facing failures for explicitly requested optional tracing."""

import sys

import pytest

from taskweaver.observability import start_langfuse


def test_partial_credentials_do_not_enable_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A partial credential pair must fail before contacting any tracing host."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "smoke-public-key")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        start_langfuse()
    assert "LANGFUSE_SECRET_KEY" in str(exc.value)


def test_missing_optional_sdk_has_installation_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default installations explain how to enable explicitly requested tracing."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "smoke-public-key")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "smoke-secret-key")
    monkeypatch.setitem(sys.modules, "langfuse", None)
    with pytest.raises(RuntimeError) as exc:
        start_langfuse()
    assert "taskweaver[observability]" in str(exc.value)
