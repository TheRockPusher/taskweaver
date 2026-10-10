"""An interrupted real SDK embedding must release its process, pipes and stores."""

import asyncio
import importlib.util
import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest

from taskweaver.agents.memory import MemoryService
from taskweaver.agents.semantic_worker import SemanticWorker
from taskweaver.config import Config


async def _embedding_response(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
    """Hold the cancellation request; serve the SDK's startup embedding normally."""
    headers = (await reader.readuntil(b"\r\n\r\n")).decode()
    length = next(
        int(line.split(":", 1)[1]) for line in headers.splitlines() if line.lower().startswith("content-length:")
    )
    request = json.loads(await reader.readexactly(length))
    if "held-for-cancellation" in str(request["input"]):
        return False
    payload = json.dumps(
        {
            "object": "list",
            "model": "embedding",
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1] * 1536}],
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        }
    ).encode()
    writer.write(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
        + str(len(payload)).encode()
        + b"\r\nConnection: close\r\n\r\n"
        + payload
    )
    await writer.drain()
    return True


async def _serve_embedding(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    started: asyncio.Event,
    disconnected: asyncio.Event,
    connections: set[asyncio.Task[None]],
) -> None:
    current = asyncio.current_task()
    assert current is not None
    connections.add(current)
    try:
        if not await _embedding_response(reader, writer):
            started.set()
            await reader.read()
            disconnected.set()
    finally:
        writer.close()
        await writer.wait_closed()
        connections.discard(current)


def _local_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, endpoint: str) -> Config:
    monkeypatch.chdir(tmp_path)
    for variable in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        monkeypatch.setenv(variable, str(tmp_path / variable))
    monkeypatch.setenv("MEM0_DIR", str(tmp_path / "sdk"))
    monkeypatch.setenv("MEM0_TELEMETRY", "False")
    monkeypatch.setenv("TASKWEAVER_API_KEY", "")
    config = Config(
        memory_enabled=True,
        database_file=tmp_path / "tasks.db",
        mem0_llm_provider="local",
        mem0_llm_model="local:causal",
        mem0_site_url=endpoint,
        mem0_embedding_provider="local",
        mem0_embedding="local:embedding",
        mem0_embedding_endpoint=endpoint,
    )
    (tmp_path / "config.toml").write_text(f'database_file = "{(tmp_path / "tasks.db").as_posix()}"\n')
    return config


async def _reopen_and_index(config: Config, db_path: Path) -> None:
    replacement = await SemanticWorker.open(config)
    try:
        memory = MemoryService(db_path, semantic_backend=replacement)
        fact = await replacement.run(lambda: memory.remember("resumed", "indexed after shutdown"))
        records = await replacement.run(memory.list_semantic)
        assert [(record.id, record.value) for record in records] == [(fact.backend_id, "indexed after shutdown")]
    finally:
        await replacement.close()


async def test_cancelled_real_embedding_releases_worker_and_reopens_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if importlib.util.find_spec("mem0") is None:
        pytest.skip("Optional semantic memory extra is not installed")

    started = asyncio.Event()
    disconnected = asyncio.Event()
    connections: set[asyncio.Task[None]] = set()

    server = await asyncio.start_server(
        lambda reader, writer: _serve_embedding(
            reader, writer, started=started, disconnected=disconnected, connections=connections
        ),
        "127.0.0.1",
        0,
    )
    assert server.sockets is not None
    endpoint = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/v1"
    config = _local_config(tmp_path, monkeypatch, endpoint)
    worker = None
    pending = None
    existing_threads = {thread.ident for thread in threading.enumerate()}
    try:
        worker = await asyncio.wait_for(SemanticWorker.open(config), 30)
        memory = MemoryService(tmp_path / "tasks.db", semantic_backend=worker)
        pending = asyncio.create_task(worker.run(lambda: memory.remember("retained", "held-for-cancellation")))
        await asyncio.wait_for(started.wait(), 10)
        # This runs on the UI's equivalent owning loop while the actual SDK HTTP
        # request is held. The authoritative local write already happened.
        assert memory.list_facts()[0].value == "held-for-cancellation"
        pending.cancel()
        await asyncio.wait_for(worker.close(), 3)
        with pytest.raises(asyncio.CancelledError):
            await pending
        await asyncio.wait_for(disconnected.wait(), 1)
        assert worker._process is not None
        assert worker._process.returncode is not None
        assert not [
            thread
            for thread in threading.enumerate()
            if thread.ident not in existing_threads and thread.name.startswith("taskweaver-semantic")
        ]
        await _reopen_and_index(config, tmp_path / "tasks.db")
        with closing(sqlite3.connect(tmp_path / "qdrant_store" / "memory_history.db")) as history:
            assert history.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert {fact.key: fact.value for fact in memory.list_facts()} == {
            "retained": "held-for-cancellation",
            "resumed": "indexed after shutdown",
        }
    finally:
        if worker is not None:
            await worker.close()
        if pending is not None:
            await asyncio.gather(pending, return_exceptions=True)
        server.close()
        await server.wait_closed()
        if connections:
            await asyncio.gather(*connections, return_exceptions=True)


async def test_semantic_chat_callbacks_preserve_mounted_ui_context(tmp_path, monkeypatch):
    if importlib.util.find_spec("mem0") is None:
        pytest.skip("Optional semantic memory extra is not installed")
    from textual.widgets import TabbedContent, TextArea  # noqa: PLC0415

    from taskweaver.agents import orchestrator  # noqa: PLC0415
    from taskweaver.tui.app import TaskWeaverApp  # noqa: PLC0415

    connections: set[asyncio.Task[None]] = set()
    server = await asyncio.start_server(
        lambda reader, writer: _serve_embedding(
            reader, writer, started=asyncio.Event(), disconnected=asyncio.Event(), connections=connections
        ),
        "127.0.0.1",
        0,
    )
    assert server.sockets is not None
    endpoint = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/v1"
    config = _local_config(tmp_path, monkeypatch, endpoint)
    monkeypatch.setattr(orchestrator, "get_config", lambda: config)
    path = tmp_path / "tasks.db"
    app = TaskWeaverApp(path)
    try:
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("4")
            app.query_one("#input-field", TextArea).load_text("/remember interface=terminal")
            await pilot.press("f2")
            async with asyncio.timeout(15):
                while not (facts := MemoryService(path).list_facts()) or not facts[0].backend_id:
                    await pilot.pause(0.01)
            await pilot.pause()
            assert [(fact.key, fact.value) for fact in facts] == [("interface", "terminal")]
            await pilot.press("ctrl+tab")
            assert app.query_one("#views", TabbedContent).active == "insights-view"
            await pilot.press("ctrl+c")
    finally:
        server.close()
        await server.wait_closed()
        if connections:
            await asyncio.gather(*connections, return_exceptions=True)
