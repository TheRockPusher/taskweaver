"""Semantic memory honors real local HTTP boundaries without cloud credential reuse."""

import importlib.util
import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from taskweaver.config import Config
from taskweaver.database import connection


def _assert_storage_reopens(vectors: Path) -> None:
    """Prove real store locks were released and the written history survives."""
    from qdrant_client import QdrantClient  # noqa: PLC0415

    with closing(QdrantClient(path=str(vectors))) as vector_client:
        vector_client.get_collections()
    with closing(sqlite3.connect(vectors / "memory_history.db")) as history:
        assert history.execute(
            "SELECT new_memory, event FROM history WHERE memory_id = ?", ("boundary-memory",)
        ).fetchone() == ("Local memory response", "ADD")


@pytest.mark.parametrize("explicit_override", [False, True])
def test_real_mem0_local_models_use_independent_anonymous_clients_and_close_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit_override: bool
) -> None:
    if importlib.util.find_spec("mem0") is None:
        pytest.skip("Optional semantic memory extra is not installed")
    # SDK storage selection happens at its first import, before constructing clients.
    data_dir = tmp_path / "application"
    vectors = data_dir / "vectors"
    sdk_dir = tmp_path / "explicit-sdk" if explicit_override else data_dir / "mem0"
    monkeypatch.setattr(connection, "get_paths", lambda: SimpleNamespace(data_dir=data_dir, qdrant_dir=vectors))
    if explicit_override:
        monkeypatch.setenv("MEM0_DIR", str(sdk_dir))
    else:
        monkeypatch.delenv("MEM0_DIR", raising=False)
    monkeypatch.setenv("MEM0_TELEMETRY", "False")
    monkeypatch.setenv("TASKWEAVER_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leave-this-process")
    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-route-to-router")

    from openai import OpenAI  # noqa: PLC0415

    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "embeddings.local":
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "model": "local-embed",
                    "data": [{"object": "embedding", "index": 0, "embedding": [0.1] * 1536}],
                    "usage": {"prompt_tokens": 3, "total_tokens": 3},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-local",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "local-causal",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Local memory response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6},
            },
        )

    def client(**kwargs):
        return OpenAI(**(kwargs | {"http_client": httpx.Client(transport=httpx.MockTransport(respond))}))

    monkeypatch.setattr("openai.OpenAI", client)
    adapter = sys.modules.get("taskweaver.database.mem0_openai")
    if adapter is not None:
        monkeypatch.setattr(adapter, "OpenAI", client)
    backend = connection.mem0_memory(
        Config(
            memory_enabled=True,
            mem0_llm_provider="local",
            mem0_llm_model="local:local-causal",
            mem0_site_url="http://causal.local/v1",
            mem0_embedding_provider="local",
            mem0_embedding="local:local-embed",
            mem0_embedding_endpoint="http://embeddings.local/v1",
        )
    )
    try:
        assert (
            backend.llm.generate_response([{"role": "user", "content": "Memory preference"}]) == "Local memory response"
        )
        assert backend.embedding_model.embed("Memory preference") == [0.1] * 1536
        assert [request.url.host for request in requests] == ["causal.local", "embeddings.local"]
        assert all("authorization" not in request.headers for request in requests)
        assert [json.loads(request.content)["model"] for request in requests] == ["local-causal", "local-embed"]
        backend.db.add_history("boundary-memory", None, "Local memory response", "ADD")
        assert backend.db.get_history("boundary-memory")[0]["new_memory"] == "Local memory response"
        assert os.environ["MEM0_DIR"] == str(sdk_dir)
    finally:
        connection.close_mem0_memory(backend)
    history_connection = backend.db.connection
    assert history_connection is not None
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        history_connection.execute("SELECT 1")
    _assert_storage_reopens(vectors)


def test_local_memory_requires_genuine_separately_configured_embedding_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TASKWEAVER_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "cloud-must-not-be-used")
    with pytest.raises(RuntimeError, match="embedding requires its own explicit endpoint"):
        connection.mem0_memory(
            Config(
                mem0_llm_provider="local",
                mem0_llm_model="local:causal",
                mem0_site_url="http://localhost:8080/v1",
                mem0_embedding_provider="local",
                mem0_embedding="local:embedding",
            )
        )


def test_explicit_database_keeps_semantic_history_out_of_default_store(tmp_path, monkeypatch):
    if importlib.util.find_spec("mem0") is None:
        pytest.skip("Optional semantic memory extra is not installed")
    default_store = tmp_path / "default" / "qdrant_store"
    selected = tmp_path / "selected" / "tasks.db"
    monkeypatch.setattr(
        connection,
        "get_paths",
        lambda: SimpleNamespace(data_dir=tmp_path / "application", qdrant_dir=default_store),
    )
    monkeypatch.setenv("MEM0_DIR", str(tmp_path / "sdk"))
    monkeypatch.setenv("TASKWEAVER_API_KEY", "")
    backend = connection.mem0_memory(
        Config(
            database_file=selected,
            mem0_llm_provider="local",
            mem0_llm_model="local:causal",
            mem0_site_url="http://127.0.0.1:9/v1",
            mem0_embedding_provider="local",
            mem0_embedding="local:embedding",
            mem0_embedding_endpoint="http://127.0.0.1:9/v1",
        )
    )
    try:
        backend.db.add_history("selected-history", None, "Selected database fact", "ADD")
    finally:
        connection.close_mem0_memory(backend)
    with closing(sqlite3.connect(selected.parent / "qdrant_store" / "memory_history.db")) as history:
        assert history.execute(
            "SELECT new_memory, event FROM history WHERE memory_id = ?", ("selected-history",)
        ).fetchone() == ("Selected database fact", "ADD")
    assert not default_store.exists()
