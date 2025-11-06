"""Observability integration with Langfuse for PydanticAI agent instrumentation.

This module provides functions to initialize Langfuse observability and check
Docker container status for Langfuse services.
"""

import re
import shutil
import subprocess

from langfuse import get_client
from loguru import logger
from pydantic_ai.agent import Agent


def is_docker_container_running(container_name: str) -> bool:
    """Check if a specific Docker container is running.

    Args:
        container_name: Name of the Docker container to check.

    Returns:
        True if container exists and is running, False otherwise.

    Raises:
        ValueError: If container_name contains invalid characters.
    """
    # Validate container name to prevent command injection (S603)
    # Container names can only contain [a-zA-Z0-9][a-zA-Z0-9_.-]*
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$", container_name):
        raise ValueError(f"Invalid container name: {container_name}")

    # Find docker executable path for security (S607)
    docker_path = shutil.which("docker")
    if not docker_path:
        logger.warning("Docker executable not found in PATH")
        return False

    try:
        # S603: subprocess call is safe here because:
        # 1. container_name is validated with regex (prevents injection)
        # 2. docker_path is resolved via shutil.which (prevents path manipulation)
        # 3. Using list args (not shell=True) prevents shell injection
        # 4. Timeout prevents hanging
        result = subprocess.run(  # noqa: S603
            [docker_path, "ps", "--filter", f"name={container_name}", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        # Check if output contains "Up" (running status)
        return "Up" in result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def start_langfuse(container_name: str = "langfuse-langfuse-web-1") -> None:
    """Initialize Langfuse client and instrument PydanticAI agents.

    Args:
        container_name: Name of the Langfuse Docker container to check (default: "langfuse-langfuse-web-1").

    Raises:
        RuntimeError: If Langfuse Docker container is not running or authentication fails.
    """
    # Check if Docker container is running
    if not is_docker_container_running(container_name):
        error_msg = f"Langfuse Docker container '{container_name}' is not running. Please start it first."
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info(f"Langfuse container '{container_name}' is running")

    # Initialize Langfuse client
    langfuse = get_client()

    if langfuse.auth_check():
        logger.info("Langfuse client is authenticated and ready!")
    else:
        error_msg = "Authentication failed. Please check your credentials and host."
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # Initialize Pydantic AI instrumentation
    Agent.instrument_all()
    logger.info("PydanticAI instrumentation enabled")
