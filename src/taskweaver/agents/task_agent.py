"""PydanticAI agent for task orchestration (placeholder)."""

from pathlib import Path

from pydantic_ai import Agent, ModelMessage

from ..config import Config, get_config
from .chat_handler import ChatHandler

# Prompts directory
PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """Load prompt from markdown file.

    Args:
        name: Prompt filename without .md extension.

    Returns:
        Prompt content as string.

    Raises:
        FileNotFoundError: If prompt file doesn't exist.

    """
    prompt_path = PROMPTS_DIR / f"{name}.md"
    return prompt_path.read_text(encoding="utf-8")


# Load system prompt
system_prompt = load_prompt("orchestrator_prompt")

# Initialize agent
config: Config = get_config()
orchestrator_agent = Agent(config.model, system_prompt=system_prompt)


def run_chat(handler: ChatHandler, db_path: Path) -> None:
    """Run interactive chat loop with the orchestrator agent.

    Args:
        handler: ChatHandler implementation for I/O operations.
        db_path: Path to the task database for agent operations.
    """
    handler.display_system_message(f"Current database path: {db_path}")
    message_history: list[ModelMessage] = []
    handler.display_system_message("🧵 TaskWeaver Chat - Type 'exit', 'quit', or Ctrl+C to end")

    while True:
        user_input = handler.get_user_input()

        if user_input is None:
            break
        if not user_input.strip():
            continue

        try:
            result = orchestrator_agent.run_sync(user_input, message_history=message_history)
            handler.display_agent_message(result.output)
            message_history = result.all_messages()
        except Exception as e:
            handler.display_error(str(e))
            raise
