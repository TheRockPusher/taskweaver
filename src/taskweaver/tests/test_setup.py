"""Tests for first-time setup wizard."""

from unittest.mock import MagicMock, patch

import pytest

from taskweaver.config import XDGPaths
from taskweaver.setup import check_configuration, run_first_time_setup


@pytest.fixture
def mock_console():
    """Mock Rich Console."""
    with patch("taskweaver.setup.console") as mock:
        yield mock


@pytest.fixture
def mock_paths(tmp_path):
    """Mock get_paths to return temporary paths."""
    # Create mock XDGPaths
    mock_paths_obj = MagicMock(spec=XDGPaths)
    mock_paths_obj.config_dir = tmp_path / "config"
    mock_paths_obj.config_dir.mkdir(parents=True, exist_ok=True)

    with patch("taskweaver.setup.get_paths", return_value=mock_paths_obj):
        yield mock_paths_obj


class TestCheckConfiguration:
    """Tests for check_configuration function."""

    def test_returns_true_when_env_exists(self, mock_paths):
        """Test check_configuration returns True when .env file exists."""
        env_file = mock_paths.config_dir / ".env"
        env_file.write_text("OPENAI_API_KEY=sk-test")

        result = check_configuration()

        assert result is True

    def test_returns_false_when_env_missing(self, mock_paths):  # noqa: ARG002
        """Test check_configuration returns False when .env file doesn't exist."""
        result = check_configuration()

        assert result is False


class TestRunFirstTimeSetup:
    """Tests for run_first_time_setup function."""

    def test_detects_existing_configuration_and_skips(self, mock_console, mock_paths):
        """Test setup detects existing .env and offers to reconfigure."""
        env_file = mock_paths.config_dir / ".env"
        env_file.write_text("OPENAI_API_KEY=sk-existing")

        with patch("taskweaver.setup.Confirm.ask", return_value=False):
            result = run_first_time_setup()

        assert result is True
        mock_console.print.assert_any_call("[green]✅ Already configured![/green]")

    def test_allows_reconfiguration_when_already_configured(self, mock_console, mock_paths):  # noqa: ARG002
        """Test setup allows reconfiguration when user confirms."""
        env_file = mock_paths.config_dir / ".env"
        env_file.write_text("OPENAI_API_KEY=sk-old")

        with (
            patch("taskweaver.setup.Confirm.ask", return_value=True),
            patch("taskweaver.setup.Prompt.ask") as mock_prompt,
        ):
            # Mock provider choice and API key
            mock_prompt.side_effect = ["1", "sk-new-key"]

            result = run_first_time_setup()

        assert result is True
        # Verify new key was written
        new_content = env_file.read_text()
        assert "sk-new-key" in new_content

    def test_openai_provider_creates_correct_files(self, mock_console, mock_paths):  # noqa: ARG002
        """Test OpenAI provider (option 1) creates correct config files."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            # Mock: provider choice = "1" (OpenAI), API key = "sk-test123"
            mock_prompt.side_effect = ["1", "sk-test123"]

            result = run_first_time_setup()

        assert result is True

        # Check .env file
        env_file = mock_paths.config_dir / ".env"
        assert env_file.exists()
        env_content = env_file.read_text()
        assert "OPENAI_API_KEY=sk-test123" in env_content
        assert "# Provider: OpenAI" in env_content

        # Check config.toml
        config_file = mock_paths.config_dir / "config.toml"
        assert config_file.exists()
        config_content = config_file.read_text()
        assert 'llm_model = "gpt-4o-mini"' in config_content

    def test_openrouter_provider_creates_correct_files(self, mock_console, mock_paths):  # noqa: ARG002
        """Test OpenRouter provider (option 2) creates correct config files."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            # Mock: provider choice = "2" (OpenRouter), API key = "sk-or-test"
            mock_prompt.side_effect = ["2", "sk-or-test"]

            result = run_first_time_setup()

        assert result is True

        # Check .env file
        env_file = mock_paths.config_dir / ".env"
        env_content = env_file.read_text()
        assert "OPENROUTER_API_KEY=sk-or-test" in env_content
        assert "# Provider: OpenRouter" in env_content

        # Check config.toml
        config_file = mock_paths.config_dir / "config.toml"
        config_content = config_file.read_text()
        assert 'llm_model = "openrouter:anthropic/claude-3.5-sonnet"' in config_content

    def test_anthropic_provider_creates_correct_files(self, mock_console, mock_paths):  # noqa: ARG002
        """Test Anthropic provider (option 3) creates correct config files."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            # Mock: provider choice = "3" (Anthropic), API key = "sk-ant-test"
            mock_prompt.side_effect = ["3", "sk-ant-test"]

            result = run_first_time_setup()

        assert result is True

        # Check .env file
        env_file = mock_paths.config_dir / ".env"
        env_content = env_file.read_text()
        assert "ANTHROPIC_API_KEY=sk-ant-test" in env_content

        # Check config.toml
        config_file = mock_paths.config_dir / "config.toml"
        config_content = config_file.read_text()
        assert 'llm_model = "anthropic:claude-3-5-sonnet-latest"' in config_content

    def test_google_provider_creates_correct_files(self, mock_console, mock_paths):  # noqa: ARG002
        """Test Google provider (option 4) creates correct config files."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            # Mock: provider choice = "4" (Google), API key = "google-api-key"
            mock_prompt.side_effect = ["4", "google-api-key"]

            result = run_first_time_setup()

        assert result is True

        # Check .env file
        env_file = mock_paths.config_dir / ".env"
        env_content = env_file.read_text()
        assert "GOOGLE_API_KEY=google-api-key" in env_content

        # Check config.toml
        config_file = mock_paths.config_dir / "config.toml"
        config_content = config_file.read_text()
        assert 'llm_model = "google-genai:gemini-1.5-flash"' in config_content

    def test_skip_option_returns_false(self, mock_console, mock_paths):
        """Test skip option (choice 5) returns False and prints instructions."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            # Mock: provider choice = "5" (Skip)
            mock_prompt.return_value = "5"

            result = run_first_time_setup()

        assert result is False

        # Check that .env was not created
        env_file = mock_paths.config_dir / ".env"
        assert not env_file.exists()

        # Check skip message was printed
        mock_console.print.assert_any_call("\n[yellow]⚠️  Skipping setup. Configure manually:[/yellow]")

    def test_empty_api_key_rejected(self, mock_console, mock_paths):
        """Test empty API key is rejected and setup cancelled."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            # Mock: provider choice = "1" (OpenAI), API key = "" (empty)
            mock_prompt.side_effect = ["1", ""]

            result = run_first_time_setup()

        assert result is False

        # Check error message was printed
        mock_console.print.assert_any_call("\n[red]❌ API key cannot be empty. Setup cancelled.[/red]")

        # Check .env was not created
        env_file = mock_paths.config_dir / ".env"
        assert not env_file.exists()

    def test_whitespace_only_api_key_rejected(self, mock_console, mock_paths):  # noqa: ARG002
        """Test whitespace-only API key is rejected."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            # Mock: provider choice = "1" (OpenAI), API key = "   " (whitespace)
            mock_prompt.side_effect = ["1", "   "]

            result = run_first_time_setup()

        assert result is False
        mock_console.print.assert_any_call("\n[red]❌ API key cannot be empty. Setup cancelled.[/red]")

    def test_api_key_whitespace_trimmed(self, mock_console, mock_paths):  # noqa: ARG002
        """Test API key whitespace is trimmed before saving."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            # Mock: provider choice = "1", API key with surrounding whitespace
            mock_prompt.side_effect = ["1", "  sk-test-with-whitespace  "]

            result = run_first_time_setup()

        assert result is True

        # Check .env file has trimmed key
        env_file = mock_paths.config_dir / ".env"
        env_content = env_file.read_text()
        assert "OPENAI_API_KEY=sk-test-with-whitespace" in env_content
        assert "  sk-test-with-whitespace  " not in env_content

    def test_config_dir_created_if_missing(self, mock_console, tmp_path):  # noqa: ARG002
        """Test config directory is created if it doesn't exist."""
        # Create paths without mkdir
        mock_paths_obj = MagicMock(spec=XDGPaths)
        mock_paths_obj.config_dir = tmp_path / "nonexistent" / "config"

        with (
            patch("taskweaver.setup.get_paths", return_value=mock_paths_obj),
            patch("taskweaver.setup.Prompt.ask") as mock_prompt,
        ):
            mock_prompt.side_effect = ["1", "sk-test"]

            result = run_first_time_setup()

        assert result is True
        assert mock_paths_obj.config_dir.exists()

    def test_does_not_overwrite_existing_config_toml(self, mock_console, mock_paths):  # noqa: ARG002
        """Test setup doesn't overwrite existing config.toml."""
        # Create existing config.toml with custom settings
        config_file = mock_paths.config_dir / "config.toml"
        existing_content = 'llm_model = "custom-model"\ncustom_setting = "value"'
        config_file.write_text(existing_content)

        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            mock_prompt.side_effect = ["1", "sk-test"]

            result = run_first_time_setup()

        assert result is True

        # Check existing config was not overwritten
        assert config_file.read_text() == existing_content

    def test_displays_provider_links(self, mock_console, mock_paths):  # noqa: ARG002
        """Test setup displays API key URL for chosen provider."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            mock_prompt.side_effect = ["1", "sk-test"]

            run_first_time_setup()

        # Check that URL was printed
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("https://platform.openai.com/api-keys" in str(call) for call in calls)

    def test_displays_success_message_with_next_steps(self, mock_console, mock_paths):  # noqa: ARG002
        """Test setup displays success message with next steps."""
        with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
            mock_prompt.side_effect = ["1", "sk-test"]

            result = run_first_time_setup()

        assert result is True

        # Check success messages
        mock_console.print.assert_any_call("\n[bold green]🎉 Setup complete![/bold green]\n")

        # Check next steps are displayed
        calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("taskweaver tui" in str(call) for call in calls)
        assert any("taskweaver chat" in str(call) for call in calls)
        assert any("taskweaver info" in str(call) for call in calls)

    def test_handles_all_provider_choices_correctly(self, mock_console, mock_paths):  # noqa: ARG002
        """Test all provider choices (1-5) are handled correctly."""
        providers = ["1", "2", "3", "4", "5"]
        expected_keys = [
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY",
            None,  # Skip option
        ]

        for choice, expected_key in zip(providers, expected_keys, strict=True):
            # Clear files between tests
            env_file = mock_paths.config_dir / ".env"
            config_file = mock_paths.config_dir / "config.toml"
            env_file.unlink(missing_ok=True)
            config_file.unlink(missing_ok=True)

            with patch("taskweaver.setup.Prompt.ask") as mock_prompt:
                if choice == "5":
                    mock_prompt.return_value = choice
                else:
                    mock_prompt.side_effect = [choice, "test-api-key"]

                result = run_first_time_setup()

            if choice == "5":
                assert result is False
                assert not env_file.exists()
            else:
                assert result is True
                assert env_file.exists()
                env_content = env_file.read_text()
                assert expected_key in env_content
