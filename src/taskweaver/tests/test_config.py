"""Tests for XDG-compliant configuration system."""

from pathlib import Path

from taskweaver import config as config_module
from taskweaver.config import (
    Config,
    XDGPaths,
    get_config,
    get_paths,
    get_project_root,
    get_xdg_cache_home,
    get_xdg_config_home,
    get_xdg_data_home,
    get_xdg_state_home,
)


def test_get_xdg_config_home_default():
    """Test XDG_CONFIG_HOME defaults to ~/.config."""
    result = get_xdg_config_home()
    assert result == Path.home() / ".config"


def test_get_xdg_config_home_override(monkeypatch):
    """Test XDG_CONFIG_HOME can be overridden."""
    custom_path = "/custom/config"
    monkeypatch.setenv("XDG_CONFIG_HOME", custom_path)
    result = get_xdg_config_home()
    assert result == Path(custom_path)


def test_get_xdg_data_home_default():
    """Test XDG_DATA_HOME defaults to ~/.local/share."""
    result = get_xdg_data_home()
    assert result == Path.home() / ".local" / "share"


def test_get_xdg_data_home_override(monkeypatch):
    """Test XDG_DATA_HOME can be overridden."""
    custom_path = "/custom/data"
    monkeypatch.setenv("XDG_DATA_HOME", custom_path)
    result = get_xdg_data_home()
    assert result == Path(custom_path)


def test_get_xdg_cache_home_default():
    """Test XDG_CACHE_HOME defaults to ~/.cache."""
    result = get_xdg_cache_home()
    assert result == Path.home() / ".cache"


def test_get_xdg_cache_home_override(monkeypatch):
    """Test XDG_CACHE_HOME can be overridden."""
    custom_path = "/custom/cache"
    monkeypatch.setenv("XDG_CACHE_HOME", custom_path)
    result = get_xdg_cache_home()
    assert result == Path(custom_path)


def test_get_xdg_state_home_default():
    """Test XDG_STATE_HOME defaults to ~/.local/state."""
    result = get_xdg_state_home()
    assert result == Path.home() / ".local" / "state"


def test_get_xdg_state_home_override(monkeypatch):
    """Test XDG_STATE_HOME can be overridden."""
    custom_path = "/custom/state"
    monkeypatch.setenv("XDG_STATE_HOME", custom_path)
    result = get_xdg_state_home()
    assert result == Path(custom_path)


def test_xdg_paths_creates_directories(monkeypatch, tmp_path):
    """Test XDGPaths creates directories on access."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    paths = XDGPaths()

    # Access properties to trigger directory creation
    config = paths.config_dir
    data = paths.data_dir
    cache = paths.cache_dir
    state = paths.state_dir

    # Verify directories were created
    assert config.exists()
    assert data.exists()
    assert cache.exists()
    assert state.exists()


def test_xdg_paths_file_paths(monkeypatch, tmp_path):
    """Test XDGPaths returns correct XDG file paths when no project detected."""
    # Create a non-project directory
    test_dir = tmp_path / "non_project"
    test_dir.mkdir()

    monkeypatch.chdir(test_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    paths = XDGPaths()

    # Should return XDG paths when no project root detected
    assert paths.config_file == tmp_path / "config" / "taskweaver" / "config.toml"
    assert paths.env_file == tmp_path / "config" / "taskweaver" / ".env"
    assert paths.database_file == tmp_path / "data" / "taskweaver" / "tasks.db"
    assert paths.log_file == tmp_path / "state" / "taskweaver" / "taskweaver.log"


def test_config_defaults():
    """Test Config default values."""
    config = Config()
    assert config.model == "gpt-4o-mini"
    assert config.api_endpoint == "https://api.openai.com/v1"
    assert config.auto_decompose is True


def test_get_config_returns_defaults_when_no_file(monkeypatch, tmp_path):
    """Test get_config returns defaults when config file doesn't exist."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    # Mock get_project_root to prevent loading project-local config

    monkeypatch.setattr(config_module, "get_project_root", lambda: None)

    # Clear cache to force reload
    get_config.cache_clear()
    get_paths.cache_clear()

    config = get_config()

    assert config.model == "gpt-4o-mini"
    assert config.api_endpoint == "https://api.openai.com/v1"


def test_get_config_loads_from_file(monkeypatch, tmp_path):
    """Test get_config loads configuration from TOML file."""
    config_dir = tmp_path / "taskweaver"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"

    # Write custom config (flat structure)
    config_file.write_text("""
model = "gpt-4"
api_endpoint = "http://localhost:1234/v1"
auto_decompose = false
""")

    # Mock get_project_root to prevent loading project-local config

    monkeypatch.setattr(config_module, "get_project_root", lambda: None)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    # Clear cache to force reload
    get_config.cache_clear()
    get_paths.cache_clear()

    config = get_config()

    assert config.model == "gpt-4"
    assert config.api_endpoint == "http://localhost:1234/v1"
    assert config.auto_decompose is False


def test_get_paths_is_cached():
    """Test get_paths returns same instance (cached)."""
    paths1 = get_paths()
    paths2 = get_paths()
    assert paths1 is paths2


def test_get_config_is_cached():
    """Test get_config returns same instance (cached)."""
    get_config.cache_clear()
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2


def test_get_project_root_finds_pyproject(tmp_path, monkeypatch):
    """Test get_project_root finds project with pyproject.toml."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").touch()

    # Change to project directory
    monkeypatch.chdir(project_dir)

    root = get_project_root()
    assert root == project_dir


def test_get_project_root_finds_git(tmp_path, monkeypatch):
    """Test get_project_root finds project with .git."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.chdir(project_dir)

    root = get_project_root()
    assert root == project_dir


def test_get_project_root_searches_parents(tmp_path, monkeypatch):
    """Test get_project_root searches parent directories."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").touch()

    # Create nested directory
    nested = project_dir / "src" / "taskweaver"
    nested.mkdir(parents=True)

    monkeypatch.chdir(nested)

    root = get_project_root()
    assert root == project_dir


def test_get_project_root_returns_none_if_not_found(tmp_path, monkeypatch):
    """Test get_project_root returns None when no project found."""
    no_project_dir = tmp_path / "random"
    no_project_dir.mkdir()

    monkeypatch.chdir(no_project_dir)

    root = get_project_root()
    assert root is None


def test_xdg_paths_project_root_detection(tmp_path, monkeypatch):
    """Test XDGPaths detects project root."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").touch()

    monkeypatch.chdir(project_dir)
    get_paths.cache_clear()

    paths = get_paths()
    assert paths.project_root == project_dir


def test_config_file_prefers_local(tmp_path, monkeypatch):
    """Test config_file returns local path when it exists."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").touch()
    local_config = project_dir / "config.toml"
    local_config.touch()

    monkeypatch.chdir(project_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    get_paths.cache_clear()

    paths = get_paths()
    assert paths.config_file == local_config


def test_config_file_falls_back_to_xdg(tmp_path, monkeypatch):
    """Test config_file returns XDG path when local doesn't exist."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").touch()
    # No local config.toml

    monkeypatch.chdir(project_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    get_paths.cache_clear()

    paths = get_paths()
    assert paths.config_file == tmp_path / "config" / "taskweaver" / "config.toml"


def test_database_file_prefers_local(tmp_path, monkeypatch):
    """Test database_file returns local path when it exists."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").touch()
    local_db = project_dir / "tasks.db"
    local_db.touch()

    monkeypatch.chdir(project_dir)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    get_paths.cache_clear()

    paths = get_paths()
    assert paths.database_file == local_db


def test_get_config_merges_local_over_xdg(tmp_path, monkeypatch):
    """Test get_config merges project-local config over XDG config."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").touch()

    # Create XDG config
    xdg_config_dir = tmp_path / "config" / "taskweaver"
    xdg_config_dir.mkdir(parents=True)
    xdg_config = xdg_config_dir / "config.toml"
    xdg_config.write_text("""
model = "gpt-4"
api_endpoint = "https://api.openai.com/v1"
auto_decompose = true
""")

    # Create local config (overrides model and endpoint)
    local_config = project_dir / "config.toml"
    local_config.write_text("""
model = "claude-3-5-sonnet-20241022"
api_endpoint = "https://api.anthropic.com/v1"
""")

    monkeypatch.chdir(project_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    get_config.cache_clear()
    get_paths.cache_clear()

    config = get_config()

    # Local overrides model and endpoint
    assert config.model == "claude-3-5-sonnet-20241022"
    assert config.api_endpoint == "https://api.anthropic.com/v1"
    # XDG auto_decompose is preserved
    assert config.auto_decompose is True


def test_api_key_from_env(monkeypatch):
    """Test config.api_key reads from API_KEY env var."""
    monkeypatch.setenv("API_KEY", "test-api-key-123")

    config = Config()
    assert config.api_key == "test-api-key-123"


def test_api_key_returns_none_when_not_set(monkeypatch):
    """Test config.api_key returns None when API_KEY not set."""
    monkeypatch.delenv("API_KEY", raising=False)

    config = Config()
    assert config.api_key is None
