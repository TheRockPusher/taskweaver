"""Real provider serialization, request routing, and deferred AI setup."""

import json

import httpx
import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import UserError

from taskweaver.agents.shared import create_agent, get_model, load_prompt
from taskweaver.config import get_config, get_paths


@pytest.fixture
def provider_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "configuration"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    for variable in (
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "TASKWEAVER_API_KEY",
    ):
        monkeypatch.delenv(variable, raising=False)
    get_config.cache_clear()
    get_paths.cache_clear()
    config_file = tmp_path / "config.toml"
    yield config_file
    get_config.cache_clear()
    get_paths.cache_clear()


def test_missing_prompt_is_actionable():
    with pytest.raises(FileNotFoundError):
        load_prompt("missing-prompt.md")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_settings", "expected_request"),
    [
        (
            ("openai", "OPENAI_API_KEY", "gpt-4o-mini"),
            ("/custom/chat/completions", "authorization", "Bearer provider-secret"),
        ),
        (
            ("openrouter", "OPENROUTER_API_KEY", "anthropic/claude-sonnet-4"),
            ("/custom/chat/completions", "authorization", "Bearer provider-secret"),
        ),
        (
            ("anthropic", "ANTHROPIC_API_KEY", "claude-sonnet-4-20250514"),
            ("/custom/v1/messages", "x-api-key", "provider-secret"),
        ),
        (
            ("google-genai", "GOOGLE_API_KEY", "gemini-2.5-flash"),
            ("/custom/v1beta/models/gemini-2.5-flash:generateContent", "x-goog-api-key", "provider-secret"),
        ),
    ],
)
async def test_real_provider_request_uses_configured_endpoint_and_key(
    monkeypatch, provider_config, provider_settings, expected_request
):
    provider, key_variable, model_name = provider_settings
    path, header, value = expected_request
    provider_config.write_text(
        f'llm_model = "{provider}:{model_name}"\napi_endpoint = "https://configured.example/custom"\n'
    )
    monkeypatch.setenv(key_variable, "provider-secret")
    if provider != "openai":
        monkeypatch.setenv("OPENAI_API_KEY", "wrong-cloud-key")
    requests = []

    def respond(request):
        requests.append(request)
        if provider == "anthropic":
            body = {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": model_name,
                "content": [{"type": "text", "text": "provider reply"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 2},
            }
        elif provider == "google-genai":
            body = {
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": "provider reply"}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 2, "totalTokenCount": 3},
            }
        else:
            body = {
                "id": "chat_test",
                "object": "chat.completion",
                "model": model_name,
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "provider reply"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(respond)

    async def handle_request(_self, request):
        return await transport.handle_async_request(request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle_request)
    result = await Agent(get_model()).run("Describe the next task")
    assert result.output == "provider reply"
    assert len(requests) == 1
    request = requests[0]
    assert request.url.host == "configured.example"
    assert request.url.path == path
    assert request.headers[header] == value
    if provider != "google-genai":
        assert json.loads(request.content)["model"] == model_name
    assert "wrong-cloud-key" not in str(request.headers)


@pytest.mark.asyncio
async def test_fresh_local_config_and_anonymous_requests_never_reuse_cloud_key(monkeypatch, provider_config):
    monkeypatch.setenv("OPENAI_API_KEY", "private-cloud-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-router-key")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chat_test",
                "object": "chat.completion",
                "model": "local-model",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "local reply"}, "finish_reason": "stop"}
                ],
            },
        )

    transport = httpx.MockTransport(respond)

    async def handle_request(_self, request):
        return await transport.handle_async_request(request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle_request)
    provider_config.write_text('llm_model="local:first-model"\napi_endpoint="http://localhost:11434/v1"\n')
    await Agent(get_model()).run("First request")
    provider_config.write_text('llm_model="local:second-model"\napi_endpoint="http://localhost:1234/api"\n')
    await Agent(get_model()).run("Second request")
    assert [request.url.port for request in requests] == [11434, 1234]
    assert [json.loads(request.content)["model"] for request in requests] == ["first-model", "second-model"]
    assert [request.url.path for request in requests] == ["/v1/chat/completions", "/api/chat/completions"]
    assert all("authorization" not in request.headers for request in requests)


@pytest.mark.parametrize(
    ("configuration", "error"),
    [
        ('llm_model="offline:none"', "AI is disabled"),
        ('llm_model="local:model"', "Local models require api_endpoint"),
        ('llm_model="unsupported:model"', "Unsupported provider"),
        ('llm_model="openai:"', "configured model is empty"),
    ],
)
def test_provider_configuration_errors_are_request_time_only(provider_config, configuration, error):
    provider_config.write_text(configuration)
    create_agent("orchestrator", [], type(None))
    with pytest.raises(UserError, match=error):
        get_model()
