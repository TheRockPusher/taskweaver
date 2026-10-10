"""Wizard persistence, secret handling, and noninteractive startup behavior."""

import os
import stat
import tomllib
from io import StringIO

import pytest
from dotenv import dotenv_values
from rich.console import Console

from taskweaver import setup
from taskweaver.config import get_config, get_paths


@pytest.fixture
def wizard(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
        monkeypatch.setenv(f"XDG_{kind}_HOME", str(tmp_path / kind.lower()))
    for variable in (
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "TASKWEAVER_API_KEY",
        "GITHUB_TOKEN",
    ):
        monkeypatch.delenv(variable, raising=False)
    output = StringIO()
    monkeypatch.setattr(setup, "console", Console(file=output, force_terminal=True))
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: True)
    get_config.cache_clear()
    get_paths.cache_clear()
    yield tmp_path, output
    get_config.cache_clear()
    get_paths.cache_clear()


def answers(monkeypatch, responses, confirms=()):
    responses = iter(responses)
    confirmations = iter(confirms)
    password_prompts = []

    def ask(prompt, **kwargs):
        if any(secret in prompt for secret in ("API_KEY", "GITHUB_TOKEN")):
            password_prompts.append(kwargs.get("password"))
        return next(responses)

    monkeypatch.setattr(setup.Prompt, "ask", ask)
    monkeypatch.setattr(setup.Confirm, "ask", lambda *_args, **_kwargs: next(confirmations))
    return password_prompts


@pytest.mark.usefixtures("wizard")
def test_non_tty_setup_never_reads_input(monkeypatch):
    monkeypatch.setattr(setup.sys.stdin, "isatty", lambda: False)

    def fail(*_args, **_kwargs):
        pytest.fail("Noninteractive startup tried to prompt")

    monkeypatch.setattr(setup.Prompt, "ask", fail)
    assert setup.run_first_time_setup() is False
    assert setup.check_configuration() is False


def test_offline_setup_refreshes_cached_database_without_env(monkeypatch, wizard):
    root, _ = wizard
    previous = get_paths().database_file
    database = root / "selected/tasks.db"
    answers(monkeypatch, ["0", str(database), ""], [False])
    assert setup.run_first_time_setup() is True
    assert setup.check_configuration() is True
    assert get_config().llm_model == "offline:none"
    assert get_config().database_file == database
    assert get_paths().database_file == database != previous
    assert not get_paths().env_file.exists()


@pytest.mark.parametrize(
    ("choice", "provider_settings"),
    [
        ("1", ("openai", "OPENAI_API_KEY", "gpt-4o-mini", "https://openai.example/v1")),
        ("2", ("openrouter", "OPENROUTER_API_KEY", "anthropic/claude-sonnet-4", "https://router.example/v1")),
        ("3", ("anthropic", "ANTHROPIC_API_KEY", "claude-sonnet-4-20250514", "https://anthropic.example")),
        ("4", ("google-genai", "GOOGLE_API_KEY", "gemini-2.5-flash", "https://google.example")),
    ],
)
def test_cloud_setup_persists_real_preferences_and_private_key(monkeypatch, wizard, choice, provider_settings):
    root, output = wizard
    provider, variable, model, endpoint = provider_settings
    secret = "secret-'quoted'-value"  # noqa: S105 - Synthetic credential exercises dotenv quoting and redaction.
    password_prompts = answers(
        monkeypatch,
        [choice, model, endpoint, secret, str(root / "tasks/custom.db"), "owner/repo", "github-private-token"],
        [False],
    )
    assert setup.run_first_time_setup() is True
    assert get_config().llm_model == f"{provider}:{model}"
    assert get_config().api_endpoint == endpoint
    assert get_config().github_repos == ["owner/repo"]
    assert get_paths().database_file == root / "tasks/custom.db"
    keys = dotenv_values(get_paths().env_file, interpolate=False)
    assert keys[variable] == secret
    assert keys["GITHUB_TOKEN"] == "github-private-token"  # noqa: S105 - Synthetic wizard input, not a real token.
    assert password_prompts == [True, True]
    assert secret not in output.getvalue()
    assert "github-private-token" not in output.getvalue()
    if os.name != "nt":
        assert stat.S_IMODE(get_paths().config_file.stat().st_mode) == 0o600
        assert stat.S_IMODE(get_paths().env_file.stat().st_mode) == 0o600


def test_repeat_setup_preserves_unknown_settings_and_other_provider_keys(monkeypatch, wizard):
    root, _ = wizard
    directory = get_paths().config_dir
    configuration = directory / "config.toml"
    configuration.write_text(
        'llm_model="openai:old"\nuser_id="personal"\ncustom_setting="retained"\n[unknown]\nvalue=42\n'
    )
    env = directory / ".env"
    env.write_text('OPENAI_API_KEY="old-secret"\nANTHROPIC_API_KEY="other-secret"\nUNRELATED="preserved"\n')
    answers(
        monkeypatch, ["2", "new-model", "https://router.example/v1", "new-secret", str(root / "new.db"), ""], [False]
    )
    assert setup.run_first_time_setup(force=True) is True
    parsed = tomllib.loads(configuration.read_text())
    assert parsed["custom_setting"] == "retained"
    assert parsed["unknown"] == {"value": 42}
    assert get_config().user_id == "personal"
    assert get_config().llm_model == "openrouter:new-model"
    keys = dotenv_values(env, interpolate=False)
    assert keys == {
        "OPENAI_API_KEY": "old-secret",
        "ANTHROPIC_API_KEY": "other-secret",
        "UNRELATED": "preserved",
        "OPENROUTER_API_KEY": "new-secret",
    }


def test_anonymous_local_setup_does_not_require_or_reuse_cloud_key(monkeypatch, wizard):
    root, _ = wizard
    monkeypatch.setenv("OPENAI_API_KEY", "private-cloud-secret")
    directory = get_paths().config_dir
    env = directory / ".env"
    env.write_text('TASKWEAVER_API_KEY="old-local-key"\n')
    answers(monkeypatch, ["5", "local-model", "http://localhost:1234/v1", "", str(root / "local.db"), ""], [False])
    assert setup.run_first_time_setup() is True
    assert get_config().llm_model == "local:local-model"
    assert dotenv_values(env, interpolate=False)["TASKWEAVER_API_KEY"] == ""
    assert os.environ["TASKWEAVER_API_KEY"] == ""
    assert "private-cloud-secret" not in env.read_text()


@pytest.mark.usefixtures("wizard")
def test_cloud_empty_key_without_existing_credential_cancels_without_writes(monkeypatch):
    answers(monkeypatch, ["1", "model", "https://api.example/v1", ""])
    assert setup.run_first_time_setup() is False
    assert not get_paths().config_file.exists()
    assert not get_paths().env_file.exists()


@pytest.mark.usefixtures("wizard")
def test_declined_reconfiguration_keeps_existing_files(monkeypatch):
    configuration = get_paths().config_file
    configuration.write_text('llm_model="offline:none"\ncustom="keep"\n')
    before = configuration.read_bytes()
    answers(monkeypatch, [], [False])
    assert setup.run_first_time_setup() is True
    assert configuration.read_bytes() == before


def test_semantic_memory_stores_separate_real_service_configuration(monkeypatch, wizard):
    root, _ = wizard
    answers(
        monkeypatch,
        [
            "0",
            str(root / "offline.db"),
            "",
            "local:memory-llm",
            "http://localhost:11434/v1",
            "",
            "local:embedding-model",
            "http://localhost:8001/v1",
        ],
        [True],
    )
    assert setup.run_first_time_setup() is True
    configuration = get_config()
    assert configuration.memory_enabled is True
    assert configuration.mem0_llm_model == "local:memory-llm"
    assert configuration.mem0_llm_provider_resolved == "openai"
    assert configuration.mem0_site_url_resolved == "http://localhost:11434/v1"
    assert configuration.mem0_embedding == "embedding-model"
    assert configuration.mem0_embedding_provider == "local"
    assert configuration.mem0_embedding_endpoint == "http://localhost:8001/v1"


def test_local_memory_without_embedding_service_does_not_persist(monkeypatch, wizard):
    root, _ = wizard
    answers(
        monkeypatch,
        [
            "0",
            str(root / "offline.db"),
            "",
            "local:memory-llm",
            "http://localhost:11434/v1",
            "",
            "local:embedding-model",
            "",
        ],
        [True],
    )
    assert setup.run_first_time_setup() is False
    assert setup.check_configuration() is False
