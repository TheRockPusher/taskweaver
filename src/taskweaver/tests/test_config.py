"""Configuration precedence and platform-native path behavior."""

from pathlib import Path

import pytest

from taskweaver import config as config_module
from taskweaver.config import XDGPaths, get_config, get_paths


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
        monkeypatch.setenv(f"XDG_{kind}_HOME", str(tmp_path / kind.lower()))
    get_config.cache_clear()
    get_paths.cache_clear()
    yield
    get_config.cache_clear()
    get_paths.cache_clear()


@pytest.mark.parametrize(
    ("platform", "expected"),
    [
        ("linux", (".config", ".local/share", ".cache", ".local/state")),
        ("darwin", ("Library/Application Support", "Library/Application Support", "Library/Caches", "Library/Logs")),
        ("win32", ("AppData/Roaming", "AppData/Local", "AppData/Local", "AppData/Local")),
    ],
)
def test_native_paths_without_xdg_overrides(monkeypatch, tmp_path, platform, expected):
    for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
        monkeypatch.delenv(f"XDG_{kind}_HOME", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(config_module.sys, "platform", platform)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    paths = XDGPaths()
    assert (paths.config_dir, paths.data_dir, paths.cache_dir, paths.state_dir) == tuple(
        tmp_path / part / "taskweaver" for part in expected
    )


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_explicit_xdg_overrides_native_defaults(monkeypatch, tmp_path, platform):
    monkeypatch.setattr(config_module.sys, "platform", platform)
    paths = XDGPaths()
    assert (paths.config_dir, paths.data_dir, paths.cache_dir, paths.state_dir) == tuple(
        tmp_path / kind / "taskweaver" for kind in ("config", "data", "cache", "state")
    )


def test_windows_environment_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module.sys, "platform", "win32")
    for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
        monkeypatch.delenv(f"XDG_{kind}_HOME", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    paths = XDGPaths()
    assert paths.config_dir == tmp_path / "roaming/taskweaver"
    assert paths.database_file == tmp_path / "local/taskweaver/tasks.db"


def test_new_git_project_does_not_capture_user_database(tmp_path):
    (tmp_path / ".git").mkdir()
    assert get_paths().database_file == tmp_path / "data/taskweaver/tasks.db"
    assert not (tmp_path / "tasks.db").exists()


def test_existing_legacy_database_survives_without_config(tmp_path):
    legacy = tmp_path / "tasks.db"
    legacy.write_bytes(b"existing user data")
    assert get_paths().database_file == legacy
    assert legacy.read_bytes() == b"existing user data"


def test_local_config_overrides_user_and_anchors_database(tmp_path, monkeypatch):
    user_dir = tmp_path / "config/taskweaver"
    user_dir.mkdir(parents=True)
    (user_dir / "config.toml").write_text(
        'llm_model = "openai:user"\nuser_id = "retained"\ndatabase_file = "user.db"\n'
    )
    project = tmp_path / "project"
    project.mkdir()
    (project / "config.toml").write_text('llm_model = "local:project"\ndatabase_file = "store/tasks.db"\n')
    nested = project / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    configuration = get_config()
    assert configuration.llm_model == "local:project"
    assert configuration.user_id == "retained"
    assert get_paths().database_file == project / "store/tasks.db"
    assert configuration.database_file == project / "store/tasks.db"


def test_user_relative_database_is_not_reanchored_by_local_config(tmp_path):
    user_dir = tmp_path / "config/taskweaver"
    user_dir.mkdir(parents=True)
    (user_dir / "config.toml").write_text('database_file = "saved.db"\n')
    (tmp_path / "config.toml").write_text('user_id = "local"\n')
    assert get_paths().database_file == user_dir / "saved.db"


def test_environment_precedence_and_refresh(tmp_path, monkeypatch):
    variable = "TASKWEAVER_API_KEY"
    monkeypatch.delenv(variable, raising=False)
    user_dir = tmp_path / "config/taskweaver"
    user_dir.mkdir(parents=True)
    (user_dir / ".env").write_text(f'{variable}="user"\n')
    (tmp_path / "config.toml").write_text('llm_model="local:model"\n')
    (tmp_path / ".env").write_text(f'{variable}="project"\n')
    get_config()
    assert config_module.os.environ[variable] == "project"
    (tmp_path / ".env").write_text(f'{variable}="updated"\n')
    get_config.cache_clear()
    get_config()
    assert config_module.os.environ[variable] == "updated"
    monkeypatch.setenv(variable, "explicit-process")
    get_config.cache_clear()
    get_config()
    assert config_module.os.environ[variable] == "explicit-process"
