"""Consumer coverage across real worker processes, HTTP transport, and SQLite."""

import asyncio
import json
import os
import select
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from github import GithubException
from pydantic import ValidationError

from taskweaver.agents import github_sync
from taskweaver.agents.chat_handler import TuiChatHandler
from taskweaver.agents.orchestrator import run_chat_async
from taskweaver.config import Config
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.connection import get_connection
from taskweaver.database.models import TaskStatus, TaskUpdate
from taskweaver.database.planning import PlanningService
from taskweaver.database.repository import TaskRepository


class LocalGitHub:
    """Serve real PyGithub JSON requests without credentials or external writes."""

    def __init__(self) -> None:
        self.issues = {}
        self.calls = []
        self.status = None
        self.hold = False
        self.hold_import = False
        self.entered = threading.Event()
        self.disconnected = threading.Event()
        self.shutdown = threading.Event()
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                pass

            def do_GET(self):
                api.calls.append(("GET", self.path))
                path = urlparse(self.path)
                if api.hold and ("/issues/" in path.path or (api.hold_import and path.path.endswith("/issues"))):
                    api.entered.set()
                    while not api.shutdown.is_set():
                        readable, _, _ = select.select([self.connection], [], [], 0.05)
                        if not readable:
                            continue
                        try:
                            closed = not self.connection.recv(1)
                        except ConnectionResetError:
                            # Windows reports a terminated client as a reset rather than EOF.
                            closed = True
                        if closed:
                            api.disconnected.set()
                            return
                    return
                status = api.status or 200
                if api.status:
                    body = {"message": "PRIVATE_BODY secret credential", "documentation_url": "private"}
                elif path.path.endswith("/issues"):
                    state = parse_qs(path.query).get("state", ["open"])[0]
                    body = [dict(issue) for issue in api.issues.values() if state == "all" or issue["state"] == state]
                elif "/issues/" in path.path:
                    body = api.issues[int(path.path.rsplit("/", 1)[1])]
                else:
                    body = {"full_name": "owner/repo", "url": f"{api.url}/repos/owner/repo"}
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_PATCH(self):
                api.calls.append(("PATCH", self.path))
                self.send_error(405)

            def do_POST(self):
                api.calls.append(("POST", self.path))
                self.send_error(405)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def add(self, number=1, **fields):
        self.issues[number] = {
            "id": 1000 + number,
            "number": number,
            "url": f"{self.url}/repos/owner/repo/issues/{number}",
            "html_url": f"https://github.com/owner/repo/issues/{number}",
            "title": f"Issue {number}",
            "body": "Original body",
            "state": "open",
            "state_reason": None,
            "updated_at": "2026-01-01T12:00:00Z",
        } | fields

    def close(self):
        self.shutdown.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def bootstrap(self, *, ignore_terminate=False):
        # Override the owned constructor's base URL only in this disposable child.
        return (
            "from github import Github; "
            "from taskweaver.agents import github_issues, github_sync; "
            f"github_issues.Github = lambda **kwargs: Github(base_url={self.url!r}, **kwargs); "
            + ("import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); " if ignore_terminate else "")
            + "github_sync._serve()"
        )


@pytest.fixture
def local_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[LocalGitHub]:
    for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
        monkeypatch.setenv(f"XDG_{kind}_HOME", str(tmp_path / kind.lower()))
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    api = LocalGitHub()
    try:
        yield api
    finally:
        api.close()


def route_child(monkeypatch, api, *, ignore_terminate=False):
    spawn = asyncio.create_subprocess_exec
    processes = []

    async def local_spawn(executable, *_args, **kwargs):
        process = await spawn(executable, "-c", api.bootstrap(ignore_terminate=ignore_terminate), **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(github_sync.asyncio, "create_subprocess_exec", local_spawn)
    return processes


async def wait_event(event):
    async with asyncio.timeout(10):
        while not event.is_set():
            await asyncio.sleep(0.01)


async def test_automatic_import_close_reopen_preserves_local_planning_and_stable_ids(local_api, monkeypatch, tmp_path):
    processes = route_child(monkeypatch, local_api)
    local_api.add()
    local_api.add(2, pull_request={"url": f"{local_api.url}/pulls/2"})
    path = tmp_path / "tasks.db"
    first = await github_sync.run_github_sync(path, ["owner/repo"])
    assert first.imported == 1
    assert first.unchanged == 1
    task_id = first.task_ids[0]
    repo = TaskRepository(path)
    goal = PlanningService(path).create_goal("Release")
    local = repo.update_task(
        task_id,
        TaskUpdate(
            duration_min=90,
            llm_value=84,
            urgency=5,
            importance=4,
            effort=2,
            goal_id=goal.goal_id,
            skill_domain="python",
            required_skill_level=4,
            requirement="Release requirements",
            category="release",
        ),
    )
    repeated = await github_sync.run_github_sync(path, ["OWNER/Repo", "owner/repo"])
    assert repeated.task_ids == first.task_ids
    assert repeated.imported == 0
    assert repeated.unchanged == 1
    local_api.issues[1].update(state="closed", state_reason="completed", title="Remote renamed")
    closed = await github_sync.run_github_sync(path, ["owner/repo"])
    assert closed.updated == 1
    task = repo.get_task(task_id)
    assert task is not None
    assert task.status is TaskStatus.COMPLETED
    assert task.title == "Remote renamed"
    for field in (
        "duration_min",
        "raw_duration_min",
        "llm_value",
        "urgency",
        "importance",
        "effort",
        "goal_id",
        "skill_domain",
        "required_skill_level",
        "requirement",
        "category",
        "priority_score",
    ):
        assert getattr(task, field) == getattr(local, field)
    assert CompletionRepository(path).get_completion_by_task_id(task_id) is None
    local_api.issues[1].update(state="open", state_reason="reopened")
    reopened = await github_sync.run_github_sync(path, ["owner/repo"])
    assert reopened.updated == 1
    assert reopened.task_ids == first.task_ids
    task = repo.get_task(task_id)
    assert task is not None
    assert task.status is TaskStatus.PENDING
    assert CompletionRepository(path).list_completions() == []
    assert len(repo.list_tasks()) == 1
    assert all(method == "GET" for method, _ in local_api.calls)
    assert all(process.returncode == 0 for process in processes)


async def test_conflicts_persist_without_overwrite_or_duplicate_reports(local_api, monkeypatch, tmp_path):
    route_child(monkeypatch, local_api)
    local_api.add()
    path = tmp_path / "tasks.db"
    first = await github_sync.run_github_sync(path, ["owner/repo"])
    task_id = first.task_ids[0]
    repo = TaskRepository(path)
    repo.update_task(task_id, TaskUpdate(title="Local title"))
    local_api.issues[1].update(title="Remote title", body="Remote body")
    result = await github_sync.run_github_sync(path, ["owner/repo"])
    assert len(result.conflicts) == 1
    assert result.updated == 1
    task = repo.get_task(task_id)
    assert task is not None
    assert task.title == "Local title"
    assert task.description == "Remote body"
    repeated = await github_sync.run_github_sync(path, ["owner/repo"])
    assert repeated.conflicts == result.conflicts
    assert repeated.task_ids == first.task_ids
    assert repeated.updated == 0
    assert all(method == "GET" for method, _ in local_api.calls)


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
async def test_http_failure_is_actionable_sanitized_and_not_retried(local_api, monkeypatch, tmp_path, status):
    processes = route_child(monkeypatch, local_api)
    local_api.status = status
    with pytest.raises(GithubException) as raised:
        await github_sync.run_github_sync(tmp_path / "tasks.db", ["owner/repo"])
    assert isinstance(raised.value, GithubException)
    assert raised.value.status == status
    assert f"HTTP {status}" in str(raised.value)
    assert "PRIVATE_BODY" not in str(raised.value)
    assert "credential" not in str(raised.value)
    assert len(local_api.calls) == 1
    assert processes[0].returncode == 0


@pytest.mark.parametrize("ignore_terminate", [False, True])
async def test_held_network_cancellation_reaps_child_and_unlocks_database(
    local_api, monkeypatch, tmp_path, ignore_terminate
):
    if ignore_terminate and os.name != "posix":
        pytest.skip("Only POSIX can deliver an ignored SIGTERM before forced termination")
    processes = route_child(monkeypatch, local_api, ignore_terminate=ignore_terminate)
    local_api.add()
    path = tmp_path / "tasks.db"
    first = await github_sync.run_github_sync(path, ["owner/repo"])
    task_id = first.task_ids[0]
    local_api.hold = True
    operation = asyncio.create_task(github_sync.run_github_sync(path, ["owner/repo"]))
    await wait_event(local_api.entered)
    operation.cancel()
    await asyncio.sleep(0)
    operation.cancel()
    async with asyncio.timeout(2):
        with pytest.raises(asyncio.CancelledError):
            await operation
    await wait_event(local_api.disconnected)
    assert processes[-1].returncode is not None
    with get_connection(path) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        assert [row["task_id"] for row in connection.execute("SELECT task_id FROM tasks")] == [str(task_id)]
    assert all(method == "GET" for method, _ in local_api.calls)


async def test_cancellation_during_spawn_keeps_ownership_until_child_is_reaped(local_api, monkeypatch, tmp_path):
    spawn = asyncio.create_subprocess_exec
    created = asyncio.Event()
    release = asyncio.Event()
    processes = []

    async def delayed_spawn(executable, *_args, **kwargs):
        process = await spawn(executable, "-c", local_api.bootstrap(), **kwargs)
        processes.append(process)
        created.set()
        await release.wait()
        return process

    monkeypatch.setattr(github_sync.asyncio, "create_subprocess_exec", delayed_spawn)
    operation = asyncio.create_task(github_sync.run_github_sync(tmp_path / "tasks.db", ["owner/repo"]))
    async with asyncio.timeout(10):
        await created.wait()
    operation.cancel()
    await asyncio.sleep(0)
    operation.cancel()
    release.set()
    async with asyncio.timeout(2):
        with pytest.raises(asyncio.CancelledError):
            await operation
    assert processes[0].returncode is not None
    assert local_api.calls == []


async def test_empty_repositories_do_not_spawn_or_touch_database(monkeypatch, tmp_path):
    async def forbidden_spawn(*_args, **_kwargs):
        pytest.fail("Empty selections must never launch an SDK worker")

    monkeypatch.setattr(github_sync.asyncio, "create_subprocess_exec", forbidden_spawn)
    path = tmp_path / "absent.db"
    result = await github_sync.run_github_sync(path, [])
    assert result.imported == 0
    assert result.task_ids == []
    assert not path.exists()


def test_sync_interval_minimum():
    assert Config(github_sync_interval_seconds=30).github_sync_interval_seconds == 30
    with pytest.raises(ValidationError):
        Config(github_sync_interval_seconds=29)


async def test_explicit_github_command_cancellation_reaps_owned_import(local_api, monkeypatch, tmp_path):
    processes = route_child(monkeypatch, local_api)
    local_api.hold = True
    local_api.hold_import = True
    messages = []
    errors = []
    systems = []

    class RecordingUI:
        def post_agent_message(self, message: str) -> None:
            messages.append(message)

        def post_error_message(self, message: str) -> None:
            errors.append(message)

        def post_system_message(self, message: str) -> None:
            systems.append(message)

    handler = TuiChatHandler(RecordingUI())
    monkeypatch.setattr("taskweaver.agents.orchestrator.get_config", lambda: Config(memory_enabled=False))
    handler.input_queue.put_nowait("/github owner/repo")
    operation = asyncio.create_task(run_chat_async(handler, tmp_path / "tasks.db"))
    try:
        # Waiting for the HTTP request also proves the chat loop remains usable
        # while this explicit command is held inside the real GitHub SDK.
        await wait_event(local_api.entered)
        operation.cancel()
        await asyncio.sleep(0)
        operation.cancel()
        async with asyncio.timeout(2):
            with pytest.raises(asyncio.CancelledError):
                await operation
        await wait_event(local_api.disconnected)
        assert processes[-1].returncode is not None
        assert messages == []
        assert errors == []
        assert all(method == "GET" for method, _ in local_api.calls)
    finally:
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)


async def test_explicit_import_does_not_pull_closed_mapped_issues(local_api, monkeypatch, tmp_path):
    route_child(monkeypatch, local_api)
    local_api.add()
    path = tmp_path / "tasks.db"
    first = await github_sync.run_github_sync(path, ["owner/repo"], import_only=True)
    local_api.issues[1].update(state="closed", state_reason="completed")
    # Initial issue parsing may fetch lazy attributes. Only the subsequent
    # empty import must avoid fetching the already-mapped closed issue.
    local_api.calls.clear()
    repeated = await github_sync.run_github_sync(path, ["owner/repo"], import_only=True)
    assert first.imported == 1
    assert repeated.imported == 0
    assert repeated.unchanged == 0
    task = TaskRepository(path).get_task(first.task_ids[0])
    assert task is not None
    assert task.status is TaskStatus.PENDING
    assert not any("/issues/" in urlparse(path).path for _, path in local_api.calls)
