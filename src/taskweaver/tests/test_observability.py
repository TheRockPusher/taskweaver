"""Tests for Langfuse observability integration."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from taskweaver.observability import is_docker_container_running, start_langfuse


class TestIsDockerContainerRunning:
    """Tests for is_docker_container_running function."""

    def test_valid_container_name_running(self):
        """Test returns True when container is running."""
        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(stdout="Up 24 minutes\n")
            result = is_docker_container_running("langfuse-web-1")
            assert result is True

    def test_valid_container_name_not_running(self):
        """Test returns False when container exists but not running."""
        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(stdout="Exited (0) 1 hour ago\n")
            result = is_docker_container_running("langfuse-web-1")
            assert result is False

    def test_invalid_container_name_raises_error(self):
        """Test raises ValueError for invalid container names."""
        with pytest.raises(ValueError, match="Invalid container name"):
            is_docker_container_running("invalid name!")

        with pytest.raises(ValueError, match="Invalid container name"):
            is_docker_container_running("../../etc/passwd")

        with pytest.raises(ValueError, match="Invalid container name"):
            is_docker_container_running("name;rm -rf /")

    def test_docker_not_found_returns_false(self):
        """Test returns False when Docker executable not found."""
        with patch("shutil.which", return_value=None):
            result = is_docker_container_running("langfuse-web-1")
            assert result is False

    def test_subprocess_error_returns_false(self):
        """Test returns False on subprocess errors."""
        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            result = is_docker_container_running("langfuse-web-1")
            assert result is False

    def test_valid_container_names_accepted(self):
        """Test various valid Docker container name formats."""
        valid_names = [
            "langfuse-web-1",
            "langfuse_web_1",
            "my.container.name",
            "Container123",
            "a1-b2_c3.d4",
        ]
        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(stdout="Up 1 minute\n")
            for name in valid_names:
                result = is_docker_container_running(name)
                assert result is True


class TestStartLangfuse:
    """Tests for start_langfuse function."""

    def test_raises_error_when_container_not_running(self):
        """Test raises RuntimeError when container is not running."""
        with (
            patch("taskweaver.observability.is_docker_container_running", return_value=False),
            pytest.raises(RuntimeError, match="not running"),
        ):
            start_langfuse()

    def test_raises_error_when_auth_fails(self):
        """Test raises RuntimeError when Langfuse auth fails."""
        with (
            patch("taskweaver.observability.is_docker_container_running", return_value=True),
            patch("taskweaver.observability.get_client") as mock_get_client,
        ):
            mock_client = MagicMock()
            mock_client.auth_check.return_value = False
            mock_get_client.return_value = mock_client

            with pytest.raises(RuntimeError, match="Authentication failed"):
                start_langfuse()

    def test_successful_initialization(self):
        """Test successful initialization when all conditions met."""
        with (
            patch("taskweaver.observability.is_docker_container_running", return_value=True),
            patch("taskweaver.observability.get_client") as mock_get_client,
            patch("taskweaver.observability.Agent") as mock_agent,
        ):
            mock_client = MagicMock()
            mock_client.auth_check.return_value = True
            mock_get_client.return_value = mock_client

            start_langfuse()

            # Verify all steps completed
            mock_get_client.assert_called_once()
            mock_client.auth_check.assert_called_once()
            mock_agent.instrument_all.assert_called_once()

    def test_custom_container_name(self):
        """Test accepts custom container name."""
        with (
            patch("taskweaver.observability.is_docker_container_running") as mock_check,
            patch("taskweaver.observability.get_client") as mock_get_client,
            patch("taskweaver.observability.Agent"),
        ):
            mock_check.return_value = True
            mock_client = MagicMock()
            mock_client.auth_check.return_value = True
            mock_get_client.return_value = mock_client

            start_langfuse(container_name="my-custom-langfuse")

            mock_check.assert_called_once_with("my-custom-langfuse")
