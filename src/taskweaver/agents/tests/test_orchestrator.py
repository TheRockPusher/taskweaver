"""Consumer-visible chat behavior through real PydanticAI FunctionModel runs."""

import asyncio
import json
import sqlite3
from collections.abc import Iterable
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from inspect import getfile
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from pydantic_ai.exceptions import UserError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from textual.widgets import TabbedContent, TextArea
from textual.worker import WorkerCancelled

from taskweaver.agents import orchestrator, shared
from taskweaver.agents.chat_handler import TuiChatHandler
from taskweaver.agents.memory import MemoryService
from taskweaver.config import Config
from taskweaver.database.models import TaskCreate
from taskweaver.database.planning import PlanningService
from taskweaver.database.repository import TaskRepository
from taskweaver.tui.app import TaskWeaverApp

pytestmark = pytest.mark.usefixtures("chat_config")


class Conversation:
    """A product I/O boundary, not a replacement for the agent or framework."""

    def __init__(self, inputs: Iterable[str | None]) -> None:
        self.inputs = iter(inputs)
        self.messages: list[str] = []
        self.errors: list[str] = []
        self.system: list[str] = []

    def get_user_input(self, prompt: str = "") -> str | None:  # noqa: ARG002
        return next(self.inputs, None)

    def display_agent_message(self, message: str) -> None:
        self.messages.append(message)

    def display_error(self, message: str) -> None:
        self.errors.append(message)

    def display_system_message(self, message: str) -> None:
        self.system.append(message)


def latest_request(messages: list[ModelMessage]) -> ModelRequest:
    return next(message for message in reversed(messages) if isinstance(message, ModelRequest))


def prompts(messages: list[ModelMessage]) -> list[str]:
    return [
        part.content
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, UserPromptPart) and isinstance(part.content, str)
    ]


@pytest.fixture
def chat_config(monkeypatch: pytest.MonkeyPatch) -> Config:
    config = Config(user_id="chat-user", memory_enabled=False)
    monkeypatch.setattr(orchestrator, "get_config", lambda: config)
    return config


def test_invalid_commands_help_focus_and_facts_work_without_credentials(tmp_path, monkeypatch) -> None:
    for key in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "TASKWEAVER_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    def forbidden_model():
        raise AssertionError("Local commands must never resolve a model")

    monkeypatch.setattr(orchestrator, "get_model", forbidden_model)
    handler = Conversation(
        [
            "/unknown",
            "/review invalid",
            "/plan",
            "/breakdown",
            "/help",
            "/review --help",
            "/remember theme=dark",
            "/memories",
            "/focus",
            "/forget theme",
            "/memories",
            None,
        ]
    )
    orchestrator.run_chat(handler, tmp_path / "chat.db")
    assert len(handler.errors) == 4
    assert any("/review TASK_UUID" in message for message in handler.messages)
    assert any("Ready work:" in message for message in handler.messages)
    assert any("theme = dark" in message for message in handler.messages)
    assert handler.messages[-1] == "No current memories."


def test_review_instructions_do_not_leak_and_successful_history_is_preserved(tmp_path, monkeypatch) -> None:
    path = tmp_path / "chat.db"
    task = TaskRepository(path).create_task(
        TaskCreate(
            title="Implement parser",
            duration_min=30,
            llm_value=60,
            requirement="Parse input",
        )
    )
    observations = []

    def provider(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        observations.append((latest_request(messages).instructions, prompts(messages)))
        return ModelResponse(parts=[TextPart("Reviewed" if len(observations) == 1 else "Normal conversation")])

    monkeypatch.setattr(orchestrator, "get_model", lambda: FunctionModel(provider))
    handler = Conversation([f"/review {task.task_id}", "How are you?", None])
    orchestrator.run_chat(handler, path)
    review_instructions, first_prompts = observations[0]
    normal_instructions, second_prompts = observations[1]
    assert "For this invocation review" in review_instructions
    assert "TaskWeaver" in review_instructions
    assert "For this invocation review" not in normal_instructions
    assert "TaskWeaver" in normal_instructions
    assert first_prompts[0] in second_prompts
    assert second_prompts[-1] == "How are you?"
    assert handler.messages == ["Reviewed", "Normal conversation"]
    assert not MemoryService(path, "chat-user").list_facts()


def test_fresh_models_and_changed_deleted_memory_apply_on_each_turn(tmp_path, monkeypatch) -> None:
    path = tmp_path / "chat.db"
    instructions = []
    resolutions = []

    def resolve_model():
        resolutions.append(len(resolutions) + 1)

        def provider(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
            instructions.append(latest_request(messages).instructions)
            return ModelResponse(parts=[TextPart(f"Provider {resolutions[-1]}")])

        return FunctionModel(provider, model_name=f"provider-{resolutions[-1]}")

    monkeypatch.setattr(orchestrator, "get_model", resolve_model)
    handler = Conversation(
        [
            "/remember theme=dark",
            "theme",
            "/remember theme=light",
            "theme",
            "/forget theme",
            "theme",
            None,
        ]
    )
    orchestrator.run_chat(handler, path)
    assert resolutions == [1, 2, 3]
    assert "Untrusted memory context" in instructions[0]
    assert '"value": "dark"' in instructions[0]
    assert '"value": "light"' in instructions[1]
    assert '"value": "dark"' not in instructions[1]
    assert "Untrusted memory context" not in instructions[2]
    assert not MemoryService(path, "chat-user").list_facts()


@pytest.mark.parametrize("mode", ["plan", "breakdown"])
def test_planning_modes_execute_real_delegated_tools(tmp_path, monkeypatch, mode) -> None:
    path = tmp_path / "chat.db"
    repo = TaskRepository(path)
    planning = PlanningService(path)
    delegated_instructions = []
    task_step = 0

    def provider(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal task_step
        tools = {tool.name for tool in info.function_tools}
        request = latest_request(messages)
        if "delegate_to_task_agent" in tools:
            if any(isinstance(part, ToolReturnPart) for part in request.parts):
                return ModelResponse(parts=[TextPart("Plan persisted through task tools")])
            return ModelResponse(parts=[ToolCallPart("delegate_to_task_agent", {"user_request": "Build a parser"})])
        delegated_instructions.append(request.instructions)
        task_step += 1
        if mode == "plan" and task_step == 1:
            return ModelResponse(parts=[ToolCallPart("create_goal_tool", {"title": "Ship parser"})])
        create_step = task_step - (1 if mode == "plan" else 0)
        if create_step in (1, 2):
            arguments = {
                "title": "Build parser" if create_step == 1 else "Test parser",
                "duration_min": 30,
                "llm_value": 70,
                "requirement": "Works",
                "category": "engineering",
            }
            if mode == "plan":
                arguments["goal_id"] = str(planning.list_goals()[0].goal_id)
            return ModelResponse(parts=[ToolCallPart("create_task_tool", arguments)])
        if create_step == 3:
            tasks = {task.title: task for task in repo.list_tasks()}
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "add_dependency_tool",
                        {
                            "task_id": str(tasks["Test parser"].task_id),
                            "blocker_id": str(tasks["Build parser"].task_id),
                        },
                    )
                ]
            )
        return ModelResponse(parts=[TextPart("Created tasks and prerequisite")])

    monkeypatch.setattr(orchestrator, "get_model", lambda: FunctionModel(provider))
    handler = Conversation([f"/{mode} Ship parser", None])
    orchestrator.run_chat(handler, path)
    assert not handler.errors
    tasks = {task.title: task for task in repo.list_tasks()}
    assert set(tasks) == {"Build parser", "Test parser"}
    assert [
        task.task_id
        for task in orchestrator.TaskDependencyRepository(path).get_blockers(
            tasks["Test parser"].task_id,
        )
    ] == [tasks["Build parser"].task_id]
    assert all("For this invocation" in instruction for instruction in delegated_instructions)
    assert all("TaskWeaver" in instruction for instruction in delegated_instructions)
    if mode == "plan":
        goal = planning.list_goals()[0]
        assert all(task.goal_id == goal.goal_id for task in tasks.values())
        assert planning.goal_progress(goal.goal_id).total == 2
    else:
        assert not planning.list_goals()


def test_research_delegation_receives_the_same_model_and_scoped_review(tmp_path, monkeypatch) -> None:
    path = tmp_path / "chat.db"
    task = TaskRepository(path).create_task(
        TaskCreate(title="Research", duration_min=10, llm_value=30, requirement="Read")
    )
    research_context = []
    resolutions = []

    def provider(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        tools = {tool.name for tool in info.function_tools}
        request = latest_request(messages)
        if "delegate_to_research_agent" in tools:
            if any(isinstance(part, ToolReturnPart) for part in request.parts):
                return ModelResponse(parts=[TextPart("Review complete")])
            return ModelResponse(
                parts=[ToolCallPart("delegate_to_research_agent", {"user_request": "Explain next steps"})]
            )
        research_context.append(request.instructions)
        return ModelResponse(parts=[TextPart("Research context reviewed")])

    def resolve():
        resolutions.append(True)
        return FunctionModel(provider)

    monkeypatch.setattr(orchestrator, "get_model", resolve)
    handler = Conversation([f"/review {task.task_id}", None])
    orchestrator.run_chat(handler, path)
    assert resolutions == [True]
    assert "For this invocation review" in research_context[0]
    assert handler.messages == ["Review complete"]


def test_provider_failure_is_visible_and_next_turn_continues_without_failed_history(tmp_path, monkeypatch) -> None:
    observations = []

    def provider(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        observations.append(prompts(messages))
        if len(observations) == 1:
            raise OSError("private provider response")
        return ModelResponse(parts=[TextPart("Recovered response")])

    monkeypatch.setattr(orchestrator, "get_model", lambda: FunctionModel(provider))
    handler = Conversation(["First request", "Second request", None])
    orchestrator.run_chat(handler, tmp_path / "chat.db")
    assert handler.messages == ["Recovered response"]
    assert "AI request failed (OSError)" in handler.errors[0]
    assert "private provider response" not in handler.errors[0]
    assert observations[1] == ["Second request"]


def test_semantic_failure_keeps_local_facts_and_closes_both_clients_and_history(
    tmp_path, monkeypatch, chat_config
) -> None:
    chat_config.memory_enabled = True
    closed = []
    history = sqlite3.connect(":memory:")

    def unavailable(*_args, **_kwargs):
        raise OSError("private fact must never be reported")

    backend = SimpleNamespace(
        add=unavailable,
        search=unavailable,
        delete=unavailable,
        get_all=unavailable,
        db=SimpleNamespace(connection=history),
        vector_store=SimpleNamespace(client=SimpleNamespace(close=lambda: closed.append("main"))),
        _telemetry_vector_store=SimpleNamespace(client=SimpleNamespace(close=lambda: closed.append("telemetry"))),
    )
    monkeypatch.setattr(orchestrator, "mem0_memory", lambda _config: backend)

    def provider(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        instructions = latest_request(messages).instructions
        assert instructions is not None
        assert '"value": "local"' in instructions
        return ModelResponse(parts=[TextPart("Used current local context")])

    monkeypatch.setattr(orchestrator, "get_model", lambda: FunctionModel(provider))
    handler = Conversation(["/remember theme=local", "theme", None])
    orchestrator.run_chat(handler, tmp_path / "chat.db")
    assert len(handler.errors) == 1
    assert "Local facts remain available" in handler.errors[0]
    assert "private fact" not in handler.errors[0]
    assert set(closed) == {"main", "telemetry"}
    with pytest.raises(sqlite3.ProgrammingError):
        history.execute("SELECT 1")
    assert MemoryService(tmp_path / "chat.db", "chat-user").list_facts()[0].value == "local"


async def test_tui_shutdown_wakes_blocked_reader_and_prevents_unmounted_callbacks() -> None:
    calls = []

    class RecordingUI:
        def post_agent_message(self, message: str) -> None:
            calls.append(("agent", message))

        def post_system_message(self, message: str) -> None:
            calls.append(("system", message))

        def post_error_message(self, message: str) -> None:
            calls.append(("error", message))

    app = RecordingUI()
    handler = TuiChatHandler(app)
    reader = asyncio.create_task(handler.get_user_input())
    await asyncio.sleep(0)
    assert not reader.done()
    handler.shutdown()
    assert await asyncio.wait_for(reader, timeout=1) is None
    handler.display_agent_message("late response")
    handler.display_error("late failure")
    handler.display_system_message("late status")
    assert not calls


@pytest.mark.parametrize("inflight", [False, True], ids=["queued-reader", "sdk-http-request"])
async def test_real_tui_quit_cancels_chat_without_late_callbacks(tmp_path, monkeypatch, chat_config, inflight) -> None:
    """Quit the mounted consumer while its real SDK transport is still blocked."""
    request_started = Event()
    disconnected = Event()
    release = Event()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:
            self.rfile.read(int(self.headers["Content-Length"]))
            requests.append(self.path)
            request_started.set()
            self.connection.settimeout(0.05)
            while not release.is_set():
                try:
                    if self.connection.recv(1) == b"":
                        disconnected.set()
                        return
                except TimeoutError:
                    continue
            # A failing implementation must still release its blocked reader on teardown.
            payload = json.dumps(
                {
                    "id": "pending-response",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "fixture",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Released only during cleanup"},
                            "finish_reason": "stop",
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()

        def log_message(self, _format, *_args) -> None:
            """Keep the isolated HTTP fixture quiet."""

    class ObservedApp(TaskWeaverApp):
        CSS_PATH = Path(getfile(TaskWeaverApp)).with_name("styles.tcss")

        def __init__(self):
            super().__init__(tmp_path / "chat.db")
            self.closing = False
            self.late_callbacks = []
            self.local_answer = asyncio.Event()

        def post_agent_message(self, message: str) -> None:
            if self.closing:
                self.late_callbacks.append(("agent", message))
            super().post_agent_message(message)
            self.local_answer.set()

        def post_system_message(self, message: str) -> None:
            if self.closing:
                self.late_callbacks.append(("system", message))
            super().post_system_message(message)

        def post_error_message(self, message: str) -> None:
            if self.closing:
                self.late_callbacks.append(("error", message))
            super().post_error_message(message)

    async def wait_for_event(event: Event) -> None:
        while not event.is_set():
            await asyncio.sleep(0.005)

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        chat_config.llm_model = "local:fixture"
        chat_config.api_endpoint = f"http://127.0.0.1:{server.server_port}/v1"
        monkeypatch.setattr(shared, "get_config", lru_cache(lambda: chat_config))
        monkeypatch.setenv("TASKWEAVER_API_KEY", "")
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        app = ObservedApp()
        try:
            async with app.run_test(size=(100, 35)) as pilot:
                app.query_one("#views", TabbedContent).active = "chat-tab"
                await pilot.pause()
                app.query_one("#input-field", TextArea).text = "Pending provider request" if inflight else "/help"
                app.action_submit_text()
                if inflight:
                    await asyncio.wait_for(wait_for_event(request_started), timeout=5)
                else:
                    await asyncio.wait_for(app.local_answer.wait(), timeout=5)
                    await asyncio.sleep(0)
                assert app.chat_started
                workers = [worker for worker in app.workers if worker.group == "chat"]
                app.closing = True
                await app.action_quit()
                assert len(workers) == 1
                with pytest.raises(WorkerCancelled):
                    await asyncio.wait_for(workers[0].wait(), timeout=1)
                assert not app.chat_started
                if inflight:
                    await asyncio.wait_for(wait_for_event(disconnected), timeout=1)
                    assert requests == ["/v1/chat/completions"]
                else:
                    assert not requests
            assert not app.late_callbacks
        finally:
            release.set()
            server.shutdown()
            server_thread.join()


def test_semantic_startup_failure_is_visible_and_local_fact_commands_continue(
    tmp_path,
    monkeypatch,
    chat_config,
) -> None:
    chat_config.memory_enabled = True

    def unavailable(_config):
        raise RuntimeError("private credential must not be printed")

    def forbidden_model():
        raise AssertionError("Local fallback commands must not resolve an AI provider")

    monkeypatch.setattr(orchestrator, "mem0_memory", unavailable)
    monkeypatch.setattr(orchestrator, "get_model", forbidden_model)
    handler = Conversation(["/remember theme=local", "/memories", None])
    orchestrator.run_chat(handler, tmp_path / "chat.db")
    assert len(handler.errors) == 1
    assert "Semantic memory could not start" in handler.errors[0]
    assert "private credential" not in handler.errors[0]
    assert "theme = local" in handler.messages[-1]


def test_worker_cancellation_discards_inflight_output_and_cleans_semantic_storage(
    tmp_path,
    monkeypatch,
    chat_config,
) -> None:
    chat_config.memory_enabled = True
    closed = []
    history = sqlite3.connect(":memory:")
    backend = SimpleNamespace(
        search=lambda *_args, **_kwargs: [],
        db=SimpleNamespace(connection=history),
        vector_store=SimpleNamespace(client=SimpleNamespace(close=lambda: closed.append("main"))),
        _telemetry_vector_store=SimpleNamespace(client=SimpleNamespace(close=lambda: closed.append("telemetry"))),
    )
    worker = SimpleNamespace(is_cancelled=False)
    monkeypatch.setattr(orchestrator, "mem0_memory", lambda _config: backend)

    def provider(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        worker.is_cancelled = True
        return ModelResponse(parts=[TextPart("Cancelled response must not be displayed")])

    monkeypatch.setattr(orchestrator, "get_model", lambda: FunctionModel(provider))
    handler = Conversation(["A request", "Must not execute", None])
    orchestrator.run_chat(handler, tmp_path / "chat.db", worker)
    assert not handler.messages
    assert set(closed) == {"main", "telemetry"}
    with pytest.raises(sqlite3.ProgrammingError):
        history.execute("SELECT 1")


def test_missing_provider_configuration_does_not_disable_local_focus(tmp_path, monkeypatch) -> None:
    def missing_model():
        raise UserError("Selected provider requires a key")

    monkeypatch.setattr(orchestrator, "get_model", missing_model)
    handler = Conversation(["Ask AI", "/focus", None])
    orchestrator.run_chat(handler, tmp_path / "chat.db")
    assert len(handler.errors) == 1
    assert "Run taskweaver setup" in handler.errors[0]
    assert "Ready work:" in handler.messages[-1]


def test_programming_error_is_not_swallowed_as_a_provider_outage(tmp_path, monkeypatch) -> None:
    def provider(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise TypeError("broken application contract")

    monkeypatch.setattr(orchestrator, "get_model", lambda: FunctionModel(provider))
    handler = Conversation(["Request", None])
    with pytest.raises(TypeError, match="broken application contract"):
        orchestrator.run_chat(handler, tmp_path / "chat.db")
    assert not handler.messages
    assert not handler.errors


@pytest.mark.parametrize("delegate", ["delegate_to_task_agent", "delegate_to_research_agent"])
def test_delegation_keeps_http_transports_owned_across_conversations(tmp_path, monkeypatch, delegate) -> None:
    """Real keep-alive requests must work within and across separate chat loops."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:
            """Respond to actual OpenAI SDK requests with a persisted tool workflow."""
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            last = request["messages"][-1]
            names = {tool["function"]["name"] for tool in request.get("tools", [])}
            message: dict = {"role": "assistant", "content": None}
            if "delegate_to_task_agent" in names and last["role"] != "tool":
                name, arguments = delegate, {"user_request": "Build a parser"}
            elif delegate == "delegate_to_task_agent" and last["role"] != "tool":
                name, arguments = (
                    "create_task_tool",
                    {
                        "title": "Parser",
                        "duration_min": 20,
                        "llm_value": 70,
                        "requirement": "Parse a valid input",
                    },
                )
            else:
                name = None
                message["content"] = (
                    last["content"]
                    if "delegate_to_task_agent" in names
                    else "Task created"
                    if delegate == "delegate_to_task_agent"
                    else "Research findings"
                )
            if name is not None:
                message["tool_calls"] = [
                    {"id": name, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}
                ]
            payload = json.dumps(
                {
                    "id": "chat-response",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "fixture",
                    "choices": [
                        {"index": 0, "message": message, "finish_reason": "tool_calls" if name is not None else "stop"}
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()

        def log_message(self, _format, *_args) -> None:
            """Keep the isolated HTTP fixture quiet."""

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        config = Config(llm_model="local:fixture", api_endpoint=f"http://127.0.0.1:{server.server_port}/v1")
        monkeypatch.setattr(shared, "get_config", lru_cache(lambda: config))
        monkeypatch.setenv("TASKWEAVER_API_KEY", "")
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conversations = [Conversation(["Build a parser", None]), Conversation(["Build a parser", None])]
            path = tmp_path / "chat.db"
            for handler in conversations:
                orchestrator.run_chat(handler, path)
        finally:
            server.shutdown()
            thread.join()
    assert all(not handler.errors for handler in conversations)
    if delegate == "delegate_to_task_agent":
        assert [handler.messages for handler in conversations] == [["Task created"], ["Task created"]]
        tasks = TaskRepository(path).list_tasks()
        assert [task.title for task in tasks] == ["Parser", "Parser"]
        assert all(task.requirement == "Parse a valid input" for task in tasks)
    else:
        assert [handler.messages for handler in conversations] == [["Research findings"], ["Research findings"]]
        assert TaskRepository(path).list_tasks() == []


async def test_async_local_command_keeps_chat_loop_responsive(tmp_path, monkeypatch) -> None:
    release = Event()
    heartbeat = asyncio.Event()
    order = []
    original = orchestrator.process_command

    def held_command(*args):
        # Only the event loop can release this; a blocked loop fails the order assertion after the timeout.
        release.wait(timeout=5)
        return original(*args)

    class AsyncConversation(Conversation):
        async def get_user_input(self, prompt: str = "") -> str | None:  # noqa: ARG002
            text = next(self.inputs, None)
            if text is None:
                await heartbeat.wait()
            return text

        def display_agent_message(self, message: str) -> None:
            order.append("response")
            super().display_agent_message(message)

    async def tick():
        await asyncio.sleep(0.05)
        order.append("heartbeat")
        heartbeat.set()
        release.set()

    monkeypatch.setattr(orchestrator, "process_command", held_command)
    handler = AsyncConversation(["/focus", None])
    await asyncio.gather(orchestrator.run_chat_async(handler, tmp_path / "chat.db"), tick())
    assert order == ["heartbeat", "response"]
    assert "Ready work:" in handler.messages[0]
