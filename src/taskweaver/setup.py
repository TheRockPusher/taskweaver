"""First-time setup wizard for TaskWeaver."""


from rich.console import Console
from rich.prompt import Confirm, Prompt

from .config import get_paths

console = Console()


def run_first_time_setup() -> bool:
    """Interactive first-time setup wizard.

    Guides user through API key configuration and creates necessary config files.

    Returns:
        True if setup completed successfully, False if skipped.

    Example:
        >>> from taskweaver.setup import run_first_time_setup
        >>> run_first_time_setup()
        🧵 Welcome to TaskWeaver!
        ...
        True
    """
    console.print("\n[bold cyan]🧵 Welcome to TaskWeaver![/bold cyan]\n")
    console.print("Let's set up your AI task organizer.\n")

    paths = get_paths()
    env_file = paths.config_dir / ".env"

    # Check if already configured
    if env_file.exists():
        console.print("[green]✅ Already configured![/green]")
        if not Confirm.ask("Reconfigure?", default=False):
            return True

    # API Key setup
    console.print("[yellow]API Key Configuration[/yellow]")
    console.print("TaskWeaver needs an LLM API key to function.\n")

    providers = {
        "1": ("OpenAI", "OPENAI_API_KEY", "https://platform.openai.com/api-keys", "gpt-4o-mini"),
        "2": (
            "OpenRouter",
            "OPENROUTER_API_KEY",
            "https://openrouter.ai/keys",
            "openrouter:anthropic/claude-3.5-sonnet",
        ),
        "3": ("Anthropic", "ANTHROPIC_API_KEY", "https://console.anthropic.com/", "anthropic:claude-3-5-sonnet-latest"),
        "4": ("Google", "GOOGLE_API_KEY", "https://makersuite.google.com/app/apikey", "google-genai:gemini-1.5-flash"),
    }

    console.print("Choose your LLM provider:")
    for key, (name, _, _, _) in providers.items():
        console.print(f"  [{key}] {name}")
    console.print("  [5] Skip (configure manually later)")

    choice = Prompt.ask("Provider", choices=["1", "2", "3", "4", "5"], default="1")

    if choice == "5":
        console.print("\n[yellow]⚠️  Skipping setup. Configure manually:[/yellow]")
        console.print(f"  {env_file}\n")
        console.print("See: https://github.com/TheRockPusher/taskweaver#configuration")
        return False

    provider_name, env_var, url, default_model = providers[choice]
    console.print(f"\n[dim]Get your API key from:[/dim] [link]{url}[/link]")

    api_key = Prompt.ask(f"\n{provider_name} API Key", password=True)

    if not api_key or api_key.strip() == "":
        console.print("\n[red]❌ API key cannot be empty. Setup cancelled.[/red]")
        return False

    # Write .env file
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    with env_file.open("w") as f:
        f.write("# TaskWeaver Configuration\n")
        f.write(f"# Provider: {provider_name}\n")
        f.write(f"{env_var}={api_key.strip()}\n")

    console.print(f"\n[green]✅ API key saved to {env_file}[/green]")

    # Create default config.toml if it doesn't exist
    config_file = paths.config_dir / "config.toml"
    if not config_file.exists():
        with config_file.open("w") as f:
            f.write("# TaskWeaver Configuration\n")
            f.write(f'llm_model = "{default_model}"\n')
            f.write("\n# Optional: GitHub integration\n")
            f.write('# github_repos = ["owner/repo"]\n')
            f.write("\n# Optional: Memory settings\n")
            f.write("# mem0_max_memories = 10\n")

        console.print(f"[green]✅ Configuration saved to {config_file}[/green]")

    console.print("\n[bold green]🎉 Setup complete![/bold green]\n")
    console.print("[dim]Try these commands:[/dim]")
    console.print("  [cyan]taskweaver tui[/cyan]      # Interactive terminal UI")
    console.print("  [cyan]taskweaver chat[/cyan]     # AI chat session")
    console.print("  [cyan]taskweaver info[/cyan]     # Show configuration\n")

    return True


def check_configuration() -> bool:
    """Check if TaskWeaver is configured with an API key.

    Returns:
        True if .env file exists in config directory, False otherwise.

    Example:
        >>> from taskweaver.setup import check_configuration
        >>> check_configuration()
        True
    """
    paths = get_paths()
    env_file = paths.config_dir / ".env"
    return env_file.exists()
